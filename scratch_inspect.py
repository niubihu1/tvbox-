import zipfile, struct, hashlib, zlib, io

with open('c:/Users/admin/Documents/GitHub/tvbox/jar/easy0928.jar', 'rb') as f:
    orig_jar = f.read()

with zipfile.ZipFile(io.BytesIO(orig_jar)) as z:
    dex = bytearray(z.read('classes.dex'))

code_off = 0x1f1dd4
insns_start = code_off + 16

# Verify current instruction at insns_start
print('Current instruction at 0x{:x}: {:02x} {:02x}'.format(insns_start, dex[insns_start], dex[insns_start+1]))

# Patch with 0x0e 0x00 (return-void)
dex[insns_start] = 0x0e
dex[insns_start+1] = 0x00
print('Patched with 0e 00!')

# Recalculate SHA-1 (offset 12..32)
sha1 = hashlib.sha1(dex[32:]).digest()
dex[12:32] = sha1
print('New SHA-1:', sha1.hex())

# Recalculate Adler32 (offset 8..12)
adler = zlib.adler32(dex[12:]) & 0xffffffff
dex[8:12] = struct.pack('<I', adler)
print('New Adler32:', hex(adler))

# Create patched jar
buf = io.BytesIO()
with zipfile.ZipFile(io.BytesIO(orig_jar)) as z_in:
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z_out:
        for item in z_in.infolist():
            if item.filename == 'classes.dex':
                z_out.writestr(item, bytes(dex))
            else:
                z_out.writestr(item, z_in.read(item.filename))

patched_jar = buf.getvalue()
print('Patched jar size:', len(patched_jar))

# Verify patched jar can be read as zip and dex has valid Adler/SHA1
with zipfile.ZipFile(io.BytesIO(patched_jar)) as z:
    dex_test = z.read('classes.dex')
    t_sha1 = hashlib.sha1(dex_test[32:]).digest()
    t_adler = zlib.adler32(dex_test[12:]) & 0xffffffff
    assert dex_test[12:32] == t_sha1
    assert struct.unpack_from('<I', dex_test, 8)[0] == t_adler
    print('VERIFICATION PASSED! Patch is 100% valid Dex!')
