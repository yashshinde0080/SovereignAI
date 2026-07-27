"""Read GGUF file header metadata"""
import struct

path = r'D:\SovereignAI\workspace\models\installed\tdh111-bitnet-b1.58-2B-4T-GGUF\bitnet1582b4t-iq2_bn.gguf'

with open(path, 'rb') as f:
    ff = f.read()

off = 0
magic = ff[off:off+4]
off += 4
version = struct.unpack('<I', ff[off:off+4])[0]; off += 4
ti = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
mk = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
print(f'Magic: {magic}, version={version}')
print(f'tensor_count={ti}, metadata_kv_count={mk}')

for i in range(min(mk, 50)):
    klen = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
    key = ff[off:off+klen].decode('utf-8'); off += klen
    kt = struct.unpack('<I', ff[off:off+4])[0]; off += 4

    if kt == 8:  # string
        slen = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
        val = ff[off:off+slen].decode('utf-8'); off += slen
    elif kt == 7:  # array
        atype = struct.unpack('<I', ff[off:off+4])[0]; off += 4
        acount = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
        if atype == 8:
            vals = []
            for _ in range(acount):
                slen = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
                vals.append(ff[off:off+slen].decode('utf-8')); off += slen
            val = vals
        elif atype == 3:  # int32 array
            import array
            val = list(array.array('i', ff[off:off+acount*4])); off += acount*4
        elif atype == 6:  # int64 array
            vals = []
            for _ in range(acount):
                vals.append(struct.unpack('<Q', ff[off:off+8])[0]); off += 8
            val = vals
        elif atype == 4:  # float32 array
            import array
            val = list(array.array('f', ff[off:off+acount*4])); off += acount*4
        else:
            val = f'<array type={atype} count={acount}>'
            off += acount * 8
    elif kt == 3:  # int32
        val = struct.unpack('<i', ff[off:off+4])[0]; off += 4
    elif kt == 4:  # float32
        val = struct.unpack('<f', ff[off:off+4])[0]; off += 4
    elif kt == 5:  # bool
        val = bool(ff[off]); off += 1
    elif kt == 2:  # float64
        val = struct.unpack('<d', ff[off:off+8])[0]; off += 8
    elif kt == 6:  # int64
        val = struct.unpack('<Q', ff[off:off+8])[0]; off += 8
    elif kt == 1:  # uint8
        val = ff[off]; off += 1
    else:
        val = f'<type {kt}>'

    print(f'  [{i}] {key} ({kt}) = {val}')
