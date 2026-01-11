from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

class HTMLReportGenerator:
    """Gera relatórios visuais avançados com gráficos de comparação entre sistemas."""

    TEMPLATE = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <title>EmuManager - Dashboard Industrial</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #121212; color: #e0e0e0; margin: 0; padding: 30px; }}
        .container {{ max-width: 1200px; margin: auto; }}
        .header {{ background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%); padding: 30px; border-radius: 12px; border-left: 8px solid #0078d4; margin-bottom: 30px; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }}
        h1 {{ margin: 0; font-size: 2.5em; letter-spacing: -1px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #333; }}
        .card h2 {{ margin: 0; color: #0078d4; font-size: 2.8em; }}
        .card p {{ margin: 10px 0 0; color: #aaa; font-weight: bold; font-size: 0.9em; }}
        
        .charts-row {{ display: grid; grid-template-columns: 1fr 2fr; gap: 30px; margin-bottom: 30px; }}
        .chart-box {{ background: #1e1e1e; padding: 25px; border-radius: 12px; border: 1px solid #333; }}
        
        /* Pie Chart */
        .pie-chart {{ width: 180px; height: 200px; border-radius: 50%; background: conic-gradient(#0078d4 {perc_comp}%, #444 0); position: relative; margin: auto; }}
        .pie-chart::after {{ content: '{perc_comp}%'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 110px; height: 110px; background: #1e1e1e; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5em; font-weight: bold; color: #0078d4; }}
        
        /* Bar Chart */
        .bar-row {{ display: flex; align-items: center; margin-bottom: 12px; }}
        .bar-label {{ width: 120px; font-size: 0.9em; color: #bbb; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .bar-container {{ flex-grow: 1; background: #333; height: 18px; border-radius: 9px; overflow: hidden; margin: 0 15px; }}
        .bar-fill {{ background: #0078d4; height: 100%; border-radius: 9px; transition: width 1s ease-in-out; }}
        .bar-value {{ width: 60px; text-align: right; font-size: 0.85em; font-weight: bold; }}

        .search-box {{ width: 100%; padding: 15px; border-radius: 10px; border: 1px solid #444; background: #1e1e1e; color: white; margin-bottom: 20px; font-size: 1em; }}
        table {{ width: 100%; border-collapse: collapse; background: #1e1e1e; border-radius: 12px; overflow: hidden; }}
        th {{ background: #0078d4; color: white; text-align: left; padding: 15px; font-size: 0.9em; text-transform: uppercase; }}
        td {{ padding: 15px; border-bottom: 1px solid #2a2a2a; font-size: 0.95em; }}
        tr:hover {{ background: #252525; }}
        .status-success {{ color: #4caf50; }}
        .status-failed {{ color: #f44336; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Dashboard de Acervo</h1>
            <p>Sessão: {task_name} | {timestamp}</p>
        </div>

        <div class="stats-grid">
            <div class="card"><h2>{success}</h2><p>Identificados</p></div>
            <div class="card"><h2>{failed}</h2><p>Erros/Ignorados</p></div>
            <div class="card"><h2>{savings_global}</h2><p>Redução de Espaço</p></div>
            <div class="card"><h2>{duration}</h2><p>Tempo Total</p></div>
        </div>

        <div class="charts-row">
            <div class="chart-box">
                <h3 style="text-align:center; margin-top:0;">EFICIÊNCIA GLOBAL</h3>
                <div class="pie-chart"></div>
                <div style="text-align:center; margin-top:20px; color:#888; font-size:0.9em;">
                    Final: {size_final} / {size_orig}
                </div>
            </div>
            <div class="chart-box">
                <h3 style="margin-top:0;">DENSIDADE POR SISTEMA (JOGOS)</h3>
                {bar_html}
            </div>
        </div>

        <input type="text" id="searchInput" class="search-box" placeholder="🔎 Pesquisar na lista de processos..." onkeyup="filterTable()">
        
        <table id="resultsTable">
            <thead>
                <tr>
                    <th>Sistema</th>
                    <th>Jogo</th>
                    <th>Status</th>
                    <th>Original</th>
                    <th>Ganho</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>

    <script>
        function filterTable() {{
            let input = document.getElementById("searchInput");
            let filter = input.value.toLowerCase();
            let table = document.getElementById("resultsTable");
            let tr = table.getElementsByTagName("tr");
            for (let i = 1; i < tr.length; i++) {{
                let text = tr[i].textContent || tr[i].innerText;
                tr[i].style.display = text.toLowerCase().indexOf(filter) > -1 ? "" : "none";
            }}
        }}
    </script>
</body>
</html>
"""

    def generate(self, result: Any, logs_dir: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.html"
        output_path = logs_dir / filename
        
        # Agrupamento por Sistema
        systems_data: Dict[str, int] = {}
        orig_total = 0
        final_total = 0
        
        for item in result.processed_items:
            sys = item.get('system', 'Outros')
            systems_data[sys] = systems_data.get(sys, 0) + 1
            orig_total += item.get('original_size', 0)
            final_total += item.get('final_size', 0)
        
        # Gerar HTML das Barras
        bar_html = ""
        if systems_data:
            max_val = max(systems_data.values())
            # Ordenar por contagem decrescente
            for sys, count in sorted(systems_data.items(), key=lambda x: x[1], reverse=True):
                perc = int((count / max_val) * 100) if max_val > 0 else 0
                bar_html += f"""
                <div class="bar-row">
                    <div class="bar-label">{sys.upper()}</div>
                    <div class="bar-container"><div class="bar-fill" style="width: {perc}%"></div></div>
                    <div class="bar-value">{count}</div>
                </div>
                """

        # Cálculos de eficiência
        perc_comp = int((final_total / orig_total * 100)) if orig_total > 0 else 100
        savings_global = f"{(1 - (final_total/orig_total))*100:.1f}%" if orig_total > 0 else "0%"
        
        def fmt_size(b): return f"{b / 1024 / 1024:.1f} MB"

        rows_html = ""
        for item in result.processed_items:
            status_class = "status-success" if item['status'] == "success" else "status-failed"
            rows_html += f"""
                <tr>
                    <td style="color:#888;">{item.get('system', 'N/A').upper()}</td>
                    <td>{item['name']}</td>
                    <td class="{status_class}">{item['status'].upper()}</td>
                    <td>{fmt_size(item['original_size'])}</td>
                    <td>{item['savings']}</td>
                </tr>
            """

        html_content = self.TEMPLATE.format(
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            task_name=result.task_name,
            success=result.success_count,
            failed=result.failed_count,
            savings_global=savings_global,
            duration=f"{result.duration_ms/1000:.1f}s",
            perc_comp=perc_comp,
            size_orig=fmt_size(orig_total),
            size_final=fmt_size(final_total),
            bar_html=bar_html,
            rows=rows_html
        )

        output_path.write_text(html_content, encoding="utf-8")
        return output_path