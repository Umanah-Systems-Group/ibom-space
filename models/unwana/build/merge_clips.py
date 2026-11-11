"""Merge all animation clips in a GLB into one clip.  python3 merge_clips.py in.glb out.glb Deploy"""
import json, struct, sys
src, dst, name = sys.argv[1], sys.argv[2], sys.argv[3]
b = open(src, 'rb').read()
L = struct.unpack('<I', b[12:16])[0]
j = json.loads(b[20:20 + L]); rest = b[20 + L:]
anims = j.get('animations', [])
if len(anims) > 1:
    merged = {'name': name, 'channels': [], 'samplers': []}
    for a in anims:
        off = len(merged['samplers'])
        merged['samplers'] += a['samplers']
        for c in a['channels']:
            c = dict(c); c['sampler'] += off; merged['channels'].append(c)
    j['animations'] = [merged]
elif anims:
    anims[0]['name'] = name
js = json.dumps(j, separators=(',', ':')).encode()
js += b' ' * ((4 - len(js) % 4) % 4)
out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + len(rest)) + struct.pack('<II', len(js), 0x4E4F534A) + js + rest
open(dst, 'wb').write(out)
print('merged', len(anims), '->', len(j.get('animations', [])), 'clip(s)')
