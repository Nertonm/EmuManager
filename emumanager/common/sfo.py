import struct

class SfoParser:
    def __init__(self, data: bytes):
        self.data = data
        self.entries = {}
        self._parse()

    def _parse(self):
        if len(self.data) < 0x14:
            return
        
        magic = self.data[0:4]
        if magic != b"\x00PSF":
            return

        key_table_start = struct.unpack("<I", self.data[8:12])[0]
        data_table_start = struct.unpack("<I", self.data[12:16])[0]
        num_entries = struct.unpack("<I", self.data[16:20])[0]

        for i in range(num_entries):
            offset = 0x14 + (i * 0x10)
            if offset + 0x10 > len(self.data):
                break
            
            key_offset = struct.unpack("<H", self.data[offset:offset+2])[0]
            data_fmt = struct.unpack("<H", self.data[offset+2:offset+4])[0]
            data_len = struct.unpack("<I", self.data[offset+4:offset+8])[0]
            data_offset = struct.unpack("<I", self.data[offset+12:offset+16])[0]

            # Read Key
            key_abs_offset = key_table_start + key_offset
            key_end = self.data.find(b"\x00", key_abs_offset)
            if key_end == -1:
                key_end = len(self.data)
            key = self.data[key_abs_offset:key_end].decode("utf-8", errors="ignore")

            # Read Data
            data_abs_offset = data_table_start + data_offset
            raw_data = self.data[data_abs_offset:data_abs_offset+data_len]

            # Format: 0x0004 = UTF8, 0x0204 = UTF8 (Null Terminated), 0x0404 = Integer
            value = None
            if data_fmt in (0x0004, 0x0204):
                value = raw_data.decode("utf-8", errors="ignore").strip("\x00")
            elif data_fmt == 0x0404 and len(raw_data) >= 4:
                value = struct.unpack("<I", raw_data[:4])[0]
            
            self.entries[key] = value

    def get(self, key: str, default=None):
        return self.entries.get(key, default)
