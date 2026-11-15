import json, sys, glob, statistics as st
files = sorted(glob.glob(sys.argv[1] + "/*.json"))
tot_hab = tot_ov = 0.0; gaps = []; turnos = []; hablantes = []; n_seg = 0; contenidos = 0; dur_max = 0
for f in files:
    segs = json.load(open(f))["segments"]; n_seg += len(segs)
    hablantes.append(len({s["speaker"] for s in segs}))
    turnos += [s["end"] - s["start"] for s in segs]
    # barrido: tiempo con >=1 y >=2 hablantes
    ev = sorted([(s["start"], 1) for s in segs] + [(s["end"], -1) for s in segs])
    act = 0; prev = None
    for t, d in ev:
        if prev is not None and act >= 1: tot_hab += t - prev
        if prev is not None and act >= 2: tot_ov += t - prev
        if prev is not None and act == 0 and t > prev: gaps.append(t - prev)
        act += d; prev = t
    # turnos contenidos enteros dentro de otro de distinto hablante
    for a in segs:
        if any(b is not a and b["speaker"] != a["speaker"] and b["start"] <= a["start"] and a["end"] <= b["end"] for b in segs):
            contenidos += 1
    dur_max = max(dur_max, max(s["end"] for s in segs))
q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
print(f"archivos {len(files)} · segmentos {n_seg} · hablantes por archivo {min(hablantes)}-{max(hablantes)}")
print(f"habla (>=1) {tot_hab:.1f} s · superpuesta (>=2) {tot_ov:.1f} s = {100*tot_ov/tot_hab:.1f} %")
print(f"turnos: mediana {st.median(turnos):.2f} s · p10 {q(turnos,.1):.2f} · p90 {q(turnos,.9):.2f} · <0,5 s: {sum(t<0.5 for t in turnos)} ({100*sum(t<0.5 for t in turnos)/len(turnos):.0f} %)")
print(f"turnos contenidos dentro de otro hablante: {contenidos} ({100*contenidos/n_seg:.0f} %)")
print(f"huecos sin hablante: {len(gaps)} · mediana {st.median(gaps):.2f} s · <0,3 s: {sum(g<0.3 for g in gaps)} ({100*sum(g<0.3 for g in gaps)/len(gaps):.0f} %) · <0,5 s: {sum(g<0.5 for g in gaps)} ({100*sum(g<0.5 for g in gaps)/len(gaps):.0f} %)")
