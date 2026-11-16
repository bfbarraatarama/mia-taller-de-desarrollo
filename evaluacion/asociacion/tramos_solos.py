import json, sys, glob, statistics as st
filas = []
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    segs = json.load(open(f))["segments"]
    ev = sorted([(s["start"], 1, s["speaker"]) for s in segs] + [(s["end"], -1, s["speaker"]) for s in segs])
    act = {}; prev = None; solos = []
    for t, d, h in ev:
        vivos = [k for k, v in act.items() if v > 0]
        if prev is not None and t > prev and len(vivos) == 1:
            if solos and solos[-1][0] == vivos[0] and abs(solos[-1][2] - prev) < 1e-9:
                solos[-1][2] = t
            else:
                solos.append([vivos[0], prev, t])
        act[h] = act.get(h, 0) + d; prev = t
    for h in sorted({s["speaker"] for s in segs}):
        d = [e - s for k, s, e in solos if k == h]
        if not d: filas.append((f, h, 0, 0, 0, 0, 0, 0)); continue
        m = st.mean(d)
        filas.append((f, h, len(d), m, max(d), sum(x >= 5 for x in d), sum(x > 15 for x in d), sum(m <= x <= 15 for x in d)))
n = len(filas)
medias = [r[3] for r in filas if r[2]]
print(f"hablantes (archivo x etiqueta): {n} · sin ningún tramo solo: {sum(r[2]==0 for r in filas)}")
print(f"media de sus tramos solos: mediana {st.median(medias):.2f} s · min {min(medias):.2f} · max {max(medias):.2f}")
print(f"hablantes cuya media es >= 5 s: {sum(m >= 5 for m in medias)} de {len(medias)}")
print(f"hablantes con algún tramo >= 5 s: {sum(r[5] > 0 for r in filas)} de {n}")
print(f"hablantes con algún tramo > 15 s: {sum(r[6] > 0 for r in filas)} · con exactamente uno > 15 s: {sum(r[6] == 1 for r in filas)}")
print(f"tramos candidatos (media <= d <= 15) por hablante: mediana {st.median([r[7] for r in filas])} · hablantes con 0 candidatos: {sum(r[7]==0 for r in filas)}")
print(f"tramos solos por hablante: mediana {st.median([r[2] for r in filas])} · min {min(r[2] for r in filas)}")
