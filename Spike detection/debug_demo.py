import requests, json, numpy as np

r = requests.get('http://127.0.0.1:5000/demo', timeout=60)
print('Status:', r.status_code)
d = r.json()

if 'error' in d:
    print('ERROR:', d['error'])
else:
    tl = d.get('loudness_timeline', [])
    ts = d.get('timestamp_timeline', [])
    print('Frames returned:', len(tl))
    if tl:
        arr = np.array(tl)
        idx = int(np.argmax(arr))
        print('Max score:', round(arr.max(), 1), 'at t=', round(ts[idx], 2) if ts else '?')
        print('Mean score:', round(arr.mean(), 1))
        print('Top 10 scores:', [round(x,1) for x in sorted(tl, reverse=True)[:10]])
    s = d.get('summary', {})
    print('Verdict:', s.get('safety_verdict'))
    print('Spikes:', s.get('total_spikes'), 'thresh:', s.get('spike_threshold'))
