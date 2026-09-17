from __future__ import annotations

"""Generate the enterprise CPG AI Discovery & Decision Intelligence artifacts.

The workbook intentionally uses plain, uncompressed mxGraphModel XML so it can
be opened and edited directly in diagrams.net/Draw.io without a CLI runtime.
The SVG and PNG are deterministic exports of the executive page.
"""

from html import escape
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "architecture"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1600, 900
COLORS = {
    "source": "#E7E9ED", "data": "#DCEBFA", "governance": "#E9DDF7",
    "decision": "#DDF2E4", "agent": "#D6F1EF", "execution": "#FBE5C7",
    "security": "#303744", "neutral": "#F5F7FA", "dark": "#172033",
    "line": "#6C778A", "accent": "#0B7D77", "red": "#B54747",
}


def make_model():
    model = Element("mxGraphModel", {
        "dx": "1600", "dy": "900", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1", "pageWidth": "1600",
        "pageHeight": "900", "math": "0", "shadow": "0",
    })
    graph_root = SubElement(model, "root")
    SubElement(graph_root, "mxCell", {"id": "0"})
    SubElement(graph_root, "mxCell", {"id": "1", "parent": "0"})
    return model


def cell(root, cid, value="", style="", x=0, y=0, w=100, h=40, parent="1", vertex=True):
    container = root.find("root") if root.tag == "mxGraphModel" else root
    attrs = {"id": cid, "value": value, "style": style, "vertex": "1" if vertex else "0", "parent": parent}
    if vertex:
        obj = SubElement(container, "mxCell", attrs)
        SubElement(obj, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
    else:
        obj = SubElement(container, "mxCell", attrs)
    return obj


def box(root, cid, label, x, y, w, h, fill="neutral", size=16, bold=True, stroke="#AEB8C5", extra=""):
    style = (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={COLORS.get(fill, fill)};"
        f"strokeColor={stroke};fontColor={COLORS['dark']};fontSize={size};"
        f"fontStyle={1 if bold else 0};spacing=8;arcSize=10;" + extra
    )
    return cell(root, cid, label, style, x, y, w, h)


def text(root, cid, label, x, y, w, h, size=16, color=None, bold=False, align="left"):
    style = f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontSize={size};fontColor={color or COLORS['dark']};fontStyle={1 if bold else 0};align={align};verticalAlign=middle;"
    return cell(root, cid, label, style, x, y, w, h)


def band(root, cid, label, x, y, w, h, fill="security", size=14):
    style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={COLORS[fill]};strokeColor={COLORS[fill]};fontColor=#FFFFFF;fontSize={size};fontStyle=1;spacing=6;arcSize=8;"
    return cell(root, cid, label, style, x, y, w, h)


def arrow(root, cid, source, target, label="", dashed=False, dotted=False, color=None):
    line = color or COLORS["line"]
    dash = "dashed=1;" if dashed else ("dashed=1;dashPattern=1 4;" if dotted else "")
    style = f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeColor={line};strokeWidth=1.5;endArrow=block;{dash}"
    obj = cell(root, cid, label, style, parent="1", vertex=False)
    obj.set("source", source); obj.set("target", target)
    if label:
        obj.set("value", label)
    SubElement(obj, "mxGeometry", {"relative": "1", "as": "geometry"})
    return obj


def title(root, name, subtitle):
    text(root, "title", escape(name), 40, 24, 1520, 42, 27, bold=True)
    text(root, "subtitle", escape(subtitle), 40, 67, 1520, 26, 14, color="#56657A")


def legend(root, x=40, y=850):
    text(root, "legend-label", "Legend", x, y, 70, 22, 12, bold=True)
    items = [("source", "Sources"), ("data", "Data"), ("governance", "Contracts / governance"), ("decision", "Decision intelligence"), ("agent", "Agentic"), ("execution", "Execution")]
    px = x + 70
    for i, (kind, label) in enumerate(items):
        box(root, f"leg-{i}", label, px, y, 145 if i != 2 else 190, 22, kind, 11, False, stroke=COLORS[kind])
        px += 155 if i != 2 else 200
    text(root, "line-legend", "solid = flow   dashed = control/governance   dotted = future/optional", 1040, y, 500, 22, 11, color="#56657A")


def page1():
    r = make_model(); title(r, "Enterprise CPG AI Discovery & Decision Intelligence", "Source-agnostic • Brand-neutral • Market-aware • Product-aware • Closed-loop")
    layers = [
        ("01", "SOURCES / SENSORS", "External AI / AEO / GEO sources<br>Retail • search • commerce • web / citations<br>Enterprise truth and master data", "source"),
        ("02", "ACQUISITION", "File • API • SFTP • event<br>Ingestion gateway • manifest • schema fingerprint", "source"),
        ("03", "GOVERNED DATA FOUNDATION", "Immutable raw evidence → Bronze → Silver canonical observations<br>Gold data products • semantic contracts • lineage", "data"),
        ("04", "DECISION INTELLIGENCE", "Governed metrics → Signals → Diagnosis + enterprise truth<br>Decision → Intervention → publish", "decision"),
        ("05", "AGENTIC / EXPERIENCE", "Web app • APIs • assistant • BI • Genie • command centre<br>Explain and retrieve; never replace deterministic controls", "agent"),
        ("06", "SYSTEMS OF EXECUTION", "Workflow • DAM • PIM • CMS / DXP<br>Commerce • retail • ESP connectors", "execution"),
        ("07", "MEASUREMENT LOOP", "Reassessment → comparable outcome → learning<br>Outcome feeds the next sensing cycle", "decision"),
    ]
    ys = [115, 205, 295, 385, 475, 565, 655]
    ids = []
    for (num, label, body, kind), y in zip(layers, ys):
        ids.append(box(r, f"p1-{num}", f"<b>{label}</b><br><font style='font-size:13px'>{body}</font>", 160, y, 1220, 64, kind, 16, True))
    for i in range(len(ids)-1): arrow(r, f"p1-a{i}", f"p1-{layers[i][0]}", f"p1-{layers[i+1][0]}")
    arrow(r, "p1-feedback", "p1-07", "p1-01", "feedback / reassessment", dotted=True, color=COLORS["accent"])
    for i, label in enumerate(["SECURITY", "GOVERNANCE", "LINEAGE", "OBSERVABILITY", "FINOPS"]):
        band(r, f"p1-cross-{i}", label, 1400 + i*34, 115, 25, 604, "security", 8)
    box(r, "p1-principle", "<b>Core distinction</b><br>External observation ≠ enterprise truth ≠ signal ≠ recommendation ≠ decision ≠ action ≠ outcome", 160, 745, 1220, 50, "neutral", 14, False, stroke=COLORS["accent"])
    legend(r)
    return r


def page2():
    r = make_model(); title(r, "Logical Platform Architecture", "Capabilities are source-agnostic; technology placement is a separate decision")
    cols = [
        ("Sources", ["AEO / GEO vendors", "Retail / search / commerce", "Web / citation data", "Product / claim / content truth", "Master / reference data"], "source"),
        ("Acquisition", ["File / API / SFTP / event", "Ingestion gateway", "Source manifest", "Schema fingerprinting", "Quarantine + replay"], "source"),
        ("Data products", ["Raw immutable", "Bronze source records", "Silver canonical observations", "Gold governed metrics", "Semantic consumption"], "data"),
        ("Control plane", ["Schema Contract Registry", "Metric Contract Registry", "Scope + Prompt registries", "Signal Rule Registry", "Version / lineage catalog"], "governance"),
        ("Intelligence", ["Signal factory", "Diagnosis", "Truth validation", "Decision", "Intervention", "Outcome"], "decision"),
        ("Experience + execution", ["Web app / APIs", "Assistant / BI / Genie", "Command centre", "Workflow", "DAM / PIM / CMS / DXP", "Commerce / retail / ESP"], "agent"),
    ]
    x = 35; widths = [220, 220, 220, 220, 220, 285]
    for i, ((label, items, kind), w) in enumerate(zip(cols, widths)):
        box(r, f"p2-h{i}", label, x, 115, w, 42, kind, 16, True)
        for j, item in enumerate(items): box(r, f"p2-{i}-{j}", item, x, 175 + j*62, w, 46, kind, 13, False)
        if i < len(cols)-1: arrow(r, f"p2-flow{i}", f"p2-{i}-{len(items)-1}", f"p2-{i+1}-0", "curated handoff")
        x += w + 25
    box(r, "p2-bottom", "Shared platform services: identity • policy • observability • data quality • cost attribution • API gateway • artifact registry • secrets", 35, 735, 1490, 54, "security", 14, True, stroke=COLORS["security"])
    legend(r)
    return r


def page3():
    r = make_model(); title(r, "Data & Schema Evolution Architecture", "Unknown schemas are isolated, explainable, replayable and never allowed to reinterpret history")
    flow = [("p3-payload", "Payload<br><font style='font-size:12px'>file / API / SFTP / event</font>", 60, 180, "source"), ("p3-manifest", "Manifest + hash", 265, 180, "source"), ("p3-fp", "Schema fingerprint", 470, 180, "governance"), ("p3-reg", "Schema Contract<br>Registry", 675, 180, "governance"), ("p3-known", "Known contract?", 880, 180, "governance")]
    for cid, label, x, y, kind in flow: box(r, cid, label, x, y, 170, 62, kind, 15)
    for a,b in zip(flow, flow[1:]): arrow(r, f"{a[0]}-{b[0]}", a[0], b[0])
    box(r, "p3-yes", "YES<br><font style='font-size:12px'>validated adapter</font>", 785, 305, 160, 58, "decision", 14)
    box(r, "p3-no", "NO<br><font style='font-size:12px'>quarantine + alert</font>", 985, 305, 160, 58, "source", 14, True, stroke=COLORS["red"])
    arrow(r, "p3-yes-a", "p3-known", "p3-yes", "known")
    arrow(r, "p3-no-a", "p3-known", "p3-no", "unknown", dashed=True, color=COLORS["red"])
    box(r, "p3-canon", "Canonicalize → Silver observation envelope<br><font style='font-size:12px'>source contract • adapter • metric contract • assessment context • row lineage</font>", 440, 410, 520, 75, "data", 15)
    arrow(r, "p3-canon-a", "p3-yes", "p3-canon")
    box(r, "p3-drift", "Schema Drift Event<br><font style='font-size:12px'>old/new fingerprint • additions/removals • type changes • sample • impact</font>", 1000, 410, 400, 75, "governance", 15, True, stroke=COLORS["red"])
    arrow(r, "p3-drift-a", "p3-no", "p3-drift")
    box(r, "p3-review", "Steward review → new contract version → replay", 1000, 545, 400, 55, "governance", 15)
    arrow(r, "p3-review-a", "p3-drift", "p3-review")
    box(r, "p3-replay", "Replay preserves original raw payload and processing versions", 1000, 650, 400, 55, "data", 15)
    arrow(r, "p3-replay-a", "p3-review", "p3-replay")
    for i, v in enumerate(["v1", "v2", "v3"]): box(r, f"p3-v{i}", f"Contract {v}<br><font style='font-size:11px'>co-existing, effective-dated</font>", 80+i*175, 560, 145, 65, "governance", 14)
    text(r, "p3-version-note", "Every canonical observation stores contract_version, adapter_version and metric_contract_version.", 55, 655, 800, 36, 14, bold=True)
    box(r, "p3-cicd", "Data / contract CI-CD<br>unit tests • schema compatibility • dbt tests • reconciliation • promotion gates", 55, 730, 800, 58, "neutral", 14)
    legend(r)
    return r


def page4():
    r = make_model(); title(r, "Signal & Decision Intelligence", "Deterministic, contract-aware computation first; language-model explanation remains a side capability")
    steps = ["Observation", "Metric contract", "Eligibility", "Baseline", "Rule", "Persistence", "Materiality", "Signal", "Diagnosis", "Enterprise truth", "Decision", "Intervention", "Outcome"]
    ids=[]
    for i,s in enumerate(steps):
        x=35+(i%7)*220; y=135+(i//7)*180
        ids.append(box(r, f"p4-{i}", s, x, y, 180, 58, "data" if i<3 else ("decision" if i>=7 else "governance"), 14))
        if i%7 and i%7 != 0: arrow(r, f"p4-a{i}", f"p4-{i-1}", f"p4-{i}")
    arrow(r, "p4-wrap", "p4-6", "p4-7", "continue")
    arrow(r, "p4-row", "p4-12", "p4-7", "reassess", dotted=True, color=COLORS["accent"])
    box(r, "p4-blocked", "BLOCKED<br><font style='font-size:12px'>unknown / unsafe semantics<br>persist finding, no action</font>", 110, 535, 270, 82, "source", 15, True, stroke=COLORS["red"])
    box(r, "p4-exp", "EXPERIMENTAL<br><font style='font-size:12px'>provisional contract<br>visible with limitation</font>", 430, 535, 270, 82, "governance", 15)
    box(r, "p4-gov", "GOVERNED<br><font style='font-size:12px'>verified semantics<br>eligible for governed action</font>", 750, 535, 270, 82, "decision", 15)
    arrow(r, "p4-branch1", "p4-2", "p4-blocked", "fails")
    arrow(r, "p4-branch2", "p4-2", "p4-exp", "provisional")
    arrow(r, "p4-branch3", "p4-2", "p4-gov", "verified")
    box(r, "p4-llm", "LLM explanation / assistant<br><font style='font-size:12px'>summarize governed evidence, limitations and options</font>", 1100, 535, 390, 82, "agent", 15)
    arrow(r, "p4-llm-a", "p4-7", "p4-llm", "side path", dotted=True, color=COLORS["accent"])
    box(r, "p4-safety", "Action gate: blocked signal or missing truth cannot create or approve an intervention. Outcomes compare only like-for-like context.", 35, 745, 1455, 54, "security", 14, True, stroke=COLORS["security"])
    legend(r)
    return r


def page5():
    r = make_model(); title(r, "Agentic Architecture", "Specialized agents consume governed tools; agents are not the signal engine or workflow store")
    box(r, "p5-users", "Business users<br>analysts • leaders • stewards", 600, 110, 400, 62, "source", 16)
    box(r, "p5-assistant", "Decision Intelligence Assistant", 600, 220, 400, 62, "agent", 17)
    arrow(r, "p5-u-a", "p5-users", "p5-assistant")
    box(r, "p5-router", "Intent router / supervisor<br><font style='font-size:12px'>policy • scope • bounded context</font>", 600, 330, 400, 70, "governance", 15)
    arrow(r, "p5-a-r", "p5-assistant", "p5-router")
    agents=[("Signal Agent", "Decision Intelligence APIs"), ("Data Agent", "Genie / governed SQL / semantic model"), ("Evidence Agent", "Evidence API / search / vector retrieval"), ("Truth Agent", "Product / claim / content truth APIs"), ("Workflow Agent", "Temporal / workflow APIs"), ("Outcome Agent", "Gold outcome data product")]
    for i,(name,tool) in enumerate(agents):
        x=55+(i%3)*510; y=470+(i//3)*110
        box(r, f"p5-ag{i}", f"<b>{name}</b><br><font style='font-size:12px'>→ {tool}</font>", x,y,420,78,"agent",14)
        arrow(r, f"p5-r-a{i}", "p5-router", f"p5-ag{i}")
    bottom=[("Model Gateway", "approved model endpoints"), ("Tool Registry", "typed permissions"), ("Policy / guardrails", "redaction + action gates"), ("Context builder", "scope + evidence pack"), ("Prompt registry", "versioned instructions"), ("Human approval", "governed action"), ("MLflow 3 / GenAI eval", "quality + cost"), ("OTel tracing", "end-to-end telemetry")]
    for i,(a,b) in enumerate(bottom):
        x=45+(i%4)*380; y=725+(i//4)*55
        box(r, f"p5-b{i}", f"{a}<br><font style='font-size:11px'>{b}</font>", x,y,330,42,"governance" if i in [1,2,4,5] else "neutral",12,False)
    box(r, "p5-callout", "Agent ≠ Workflow Engine   •   Genie ≠ Decision Engine   •   LLM ≠ Signal Engine", 45, 835, 1420, 32, "security", 13, True, stroke=COLORS["security"])
    return r


def page6():
    r = make_model(); title(r, "Kenvue Technology Mapping", "Technology candidates are implementation choices; the logical architecture remains platform-independent")
    headers=["CAPABILITY", "GENERIC TECHNOLOGY ROLE", "KENVUE TECHNOLOGY CANDIDATE", "NOTES"]
    xs=[30,350,745,1120]; ws=[300,370,350,430]
    for i,h in enumerate(headers): box(r, f"p6-h{i}", h, xs[i], 115, ws[i], 42, "governance", 14)
    rows=[
        ("Cloud platform / runtime", "Cloud + container runtime", "Azure / K-Cloud; AKS", "Private networking and approved standards"),
        ("Lakehouse / governance", "Enterprise data platform", "Databricks + Delta Lake + Unity Catalog", "Bronze/Silver/Gold/semantic products"),
        ("Transform / orchestration", "Versioned transforms + jobs", "dbt + Lakeflow / Databricks Jobs", "Quality and promotion gates"),
        ("Workflow / API / operations", "Durable workflow + APIs + OLTP", "Temporal + Kong + PostgreSQL + Redis", "Keep transaction state out of analytics"),
        ("Messaging / storage", "Event transport + object landing", "Azure Service Bus / Event Hub + governed storage", "File/API/event adapters converge"),
        ("Search / models / agents", "Retrieval + approved model access", "Azure AI Search / Vector Search + enterprise LLM endpoints", "Pluggable agent framework"),
        ("Conversational analytics", "Governed NL structured-data analysis", "Databricks Genie", "Not signal, workflow, truth or approval engine"),
        ("Security / delivery / telemetry", "Secrets, CI/CD, evaluation, tracing", "Key Vault + Nexus + enterprise pipelines/Git + MLflow 3 + OTel", "Audit, redaction, cost and quality"),
        ("Consumption", "Enterprise intelligence experience", "Command Centre / KIIP where appropriate", "Candidate channel; not a logical dependency"),
    ]
    for row,(a,b,c,d) in enumerate(rows):
        y=168+row*68
        for i,val in enumerate((a,b,c,d)):
            box(r, f"p6-{row}-{i}", val, xs[i], y, ws[i], 56, "neutral" if i in [0,3] else ("data" if i==1 else "agent"), 12, False)
    text(r, "p6-footer", "Technology placement subject to approved enterprise standards. Logical architecture is platform-independent.", 30, 800, 1450, 30, 13, color="#56657A", bold=True)
    legend(r)
    return r


def page7():
    r = make_model(); title(r, "Runtime / Deployment View", "Trust boundaries, private service paths and model access controls")
    boundaries=[("USER NETWORK", 30, 125, 240, 570, "source"), ("EDGE", 295, 125, 220, 570, "governance"), ("APPLICATION VNET", 540, 125, 540, 570, "agent"), ("DATA PLATFORM", 1105, 125, 260, 570, "data"), ("ENTERPRISE SYSTEMS", 1390, 125, 180, 570, "execution")]
    for i,(label,x,y,w,h,kind) in enumerate(boundaries):
        box(r, f"p7-bound{i}", label, x,y,w,42,kind,13,True)
    services=[("Browser", "p7-bound0", 65, 230, 170, 52, "source"), ("Identity / Entra ID", "p7-bound1", 320, 230, 170, 52, "governance"), ("WAF / Kong API Gateway", "p7-bound1", 320, 350, 170, 52, "governance"), ("AKS Ingress", "p7-bound2", 600, 205, 170, 52, "agent"), ("Frontend / API / Agent Services", "p7-bound2", 600, 320, 300, 62, "agent"), ("PostgreSQL / Redis / Temporal", "p7-bound2", 600, 455, 300, 62, "execution"), ("Databricks APIs / SQL / Genie", "p7-bound3", 1145, 270, 180, 62, "data"), ("Object storage / Unity Catalog", "p7-bound3", 1145, 420, 180, 62, "data"), ("Truth / DAM / PIM / CMS", "p7-bound4", 1398, 300, 155, 62, "execution")]
    for i,(name,parent,x,y,w,h,kind) in enumerate(services): box(r, f"p7-s{i}", name, x,y,w,h,kind,13,False)
    for a,b,label in [("p7-s0","p7-s1","identity"),("p7-s1","p7-s2","authorize"),("p7-s2","p7-s3","route"),("p7-s3","p7-s4","private service"),("p7-s4","p7-s5","state / workflow"),("p7-s4","p7-s6","curated data"),("p7-s6","p7-s7","read / write"),("p7-s4","p7-s8","truth APIs")]: arrow(r, f"p7-a-{a}-{b}", a,b,label)
    box(r, "p7-model", "Agent Service → Model Access Control → approved model endpoints", 600, 620, 700, 58, "security", 14, True, stroke=COLORS["security"])
    arrow(r, "p7-model-a", "p7-s4", "p7-model", "controlled model call", dashed=True, color=COLORS["red"])
    box(r, "p7-cicd", "Nexus → CI/CD → AKS<br><font style='font-size:12px'>signed artifacts • tests • promotion • rollback</font>", 45, 745, 650, 62, "governance", 14)
    box(r, "p7-net", "Private networking where applicable • no unrestricted raw-data access from agents", 745, 745, 800, 62, "security", 14, True, stroke=COLORS["security"])
    legend(r)
    return r


def page8():
    r=make_model(); title(r,"End-to-End Sequence","Observation-to-outcome lifecycle with an explicit unknown-schema exception path")
    actors=["External vendor","Acquisition","Object storage","Databricks","Schema registry","Signal engine","Decision API","Assistant","Business user","Workflow","Truth / content platform","Reassessment"]
    xs=[]
    for i,a in enumerate(actors):
        x=25+i*128; xs.append(x)
        box(r,f"p8-a{i}",a,x,105,112,44,"source" if i==0 else "neutral",11,True)
        text(r,f"p8-line{i}","",x+55,150,1,560,1)
    events=[
        ("p8-e1",1,2,"1 vendor assessment arrives"),("p8-e2",2,3,"2 immutable landing + hash"),("p8-e3",3,4,"3 schema fingerprint / lookup"),("p8-e4",4,3,"4 known → adapter / unknown → quarantine"),("p8-e5",3,5,"5 parse + canonicalize"),("p8-e6",5,6,"6 metric validation + signal"),("p8-e7",6,7,"7 diagnosis / truth context"),("p8-e8",7,8,"8 user / agent review"),("p8-e9",8,6,"9 business decision"),("p8-e10",6,9,"10 intervention workflow"),("p8-e11",9,10,"11 publish downstream"),("p8-e12",10,11,"12 schedule reassessment"),("p8-e13",11,3,"13 ingest next measurement"),("p8-e14",3,5,"14 comparable outcome / close loop")]
    for i,(cid,a,b,label) in enumerate(events):
        y=195+i*39
        arrow(r,cid,f"p8-line{a}",f"p8-line{b}",label, color=COLORS["accent"] if i in [5,8,13] else None)
    box(r,"p8-exception","Exception: unknown schema → quarantine → schema drift event → contract update → replay",420,760,700,56,"source",14,True,stroke=COLORS["red"])
    legend(r)
    return r


def page9():
    r=make_model(); title(r,"Security, Governance & Observability","Controls are layered across the platform; governance is not a single approval box")
    controls=["Identity","Data security","API security","AI security","Secrets","Network","Audit","Lineage","Data quality","Agent evaluation","App observability","FinOps","Retention","DR"]
    layers=[("Experience / agents", "agent"),("APIs / workflow", "execution"),("Decision intelligence", "decision"),("Semantic / gold", "governance"),("Silver / bronze", "data"),("Raw / landing", "source")]
    x0=260; colw=88
    for i,c in enumerate(controls): box(r,f"p9-h{i}",c, x0+i*colw, 110, colw-5, 92, "security", 10, True, stroke=COLORS["security"])
    for j,(l,kind) in enumerate(layers):
        y=220+j*78; box(r,f"p9-l{j}",l,30,y,210,52,kind,13)
        for i in range(len(controls)):
            fill="security" if i in [0,1,2,3,4,5,6] and j in [0,1,2] else ("governance" if i in [7,8,9] else "neutral")
            label="●" if fill != "neutral" else "–"
            box(r,f"p9-{j}-{i}",label,x0+i*colw,y,colw-5,52,fill,16,True,stroke="#D3D9E2")
    box(r,"p9-note","Every layer emits lineage, audit and telemetry. Raw evidence is immutable; agents receive scoped, governed context; action requires policy and human approval where configured.",30,720,1460,58,"security",14,True,stroke=COLORS["security"])
    text(r,"p9-foot","● control applied   – not the primary control plane",30,800,600,25,12,color="#56657A")
    legend(r)
    return r


def page10():
    r=make_model(); title(r,"Scale & Multi-Tenant Model","One configuration-driven platform supports many markets, brands, products, sources and prompts")
    markets=[("Market A","Brands 1..N<br>Products / SKUs 1..N", "#E8F2FB"),("Market B","Brands 1..N<br>Products / SKUs 1..N", "#E8F2FB"),("Market C","Brands 1..N<br>Products / SKUs 1..N", "#E8F2FB")]
    for i,(name,body,_) in enumerate(markets): box(r,f"p10-m{i}",f"<b>{name}</b><br><font style='font-size:13px'>{body}</font>",60+i*260,170,220,110,"data",16)
    box(r,"p10-shared","SHARED PLATFORM<br><font style='font-size:14px'>Canonical model • contract registries • rules • platform services • lineage • observability • FinOps</font>",470,170,660,110,"decision",18)
    for i in range(3): arrow(r,f"p10-m-a{i}",f"p10-m{i}","p10-shared","config + data products")
    configs=["market policy","language","brand / product scope","prompt library","rules + threshold profile","truth sources","activation connectors"]
    for i,c in enumerate(configs): box(r,f"p10-c{i}",c,50+(i%4)*370,390+(i//4)*78,330,54,"governance",13)
    for i in range(len(configs)): arrow(r,f"p10-c-a{i}","p10-shared",f"p10-c{i}","configure",dashed=True)
    box(r,"p10-onboard","New Market + New Brand + New Source Contract → same platform",410,620,780,62,"agent",17,True)
    box(r,"p10-avoid","Avoid one deployment per brand or one pipeline per CSV; isolate only when policy genuinely requires it.",260,735,1060,54,"security",14,True,stroke=COLORS["security"])
    box(r,"p10-scale","Target orders of magnitude: 100s brands • 10s markets • 10,000s products/SKUs • 100,000s prompts • multiple AI engines • daily/weekly assessments • multi-year history",130,815,1340,40,"neutral",13,False)
    legend(r)
    return r


PAGES = [
    ("01 — Executive Reference Architecture", page1),
    ("02 — Logical Platform Architecture", page2),
    ("03 — Data & Schema Evolution Architecture", page3),
    ("04 — Signal & Decision Intelligence", page4),
    ("05 — Agentic Architecture", page5),
    ("06 — Kenvue Technology Mapping", page6),
    ("07 — Runtime / Deployment View", page7),
    ("08 — End-to-End Sequence", page8),
    ("09 — Security, Governance & Observability", page9),
    ("10 — Scale & Multi-Tenant Model", page10),
]


def write_drawio():
    root = Element("mxfile", {"host": "app.diagrams.net", "modified": "2026-08-08T00:00:00.000Z", "agent": "Codex", "version": "24.7.17", "type": "device"})
    for name, fn in PAGES:
        diag = SubElement(root, "diagram", {"id": name[:2].replace(" ", "-") + "-cpg", "name": name})
        model = fn(); diag.append(model)
    ElementTree(root).write(OUT / "CPG_Decision_Intelligence_Target_Architecture.drawio", encoding="utf-8", xml_declaration=True)


def page1_svg():
    layers = [
        ("SOURCES / SENSORS", "External AI / AEO / GEO sources • retail/search/commerce • enterprise truth", "#E7E9ED"),
        ("ACQUISITION", "File • API • SFTP • event • ingestion gateway • schema fingerprint", "#E7E9ED"),
        ("GOVERNED DATA FOUNDATION", "Immutable raw evidence → Bronze → Silver canonical observations → Gold / semantic", "#DCEBFA"),
        ("DECISION INTELLIGENCE", "Governed metrics → Signals → Diagnosis + enterprise truth → Decision", "#DDF2E4"),
        ("AGENTIC / EXPERIENCE", "Web app • APIs • assistant • BI • Genie • command centre", "#D6F1EF"),
        ("SYSTEMS OF EXECUTION", "Workflow • DAM • PIM • CMS / DXP • commerce / retail / ESP", "#FBE5C7"),
        ("MEASUREMENT LOOP", "Reassessment → comparable outcome → learning → next sensing cycle", "#DDF2E4"),
    ]
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="100%" height="100%" fill="#ffffff"/>', '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172033}.title{font-size:28px;font-weight:700}.sub{font-size:15px;fill:#56657A}.layer{font-size:17px;font-weight:700}.body{font-size:14px;fill:#344054}.small{font-size:12px;fill:#56657A}</style>']
    svg.append('<text x="40" y="42" class="title">Enterprise CPG AI Discovery &amp; Decision Intelligence</text>')
    svg.append('<text x="40" y="68" class="sub">Source-agnostic • Brand-neutral • Market-aware • Product-aware • Closed-loop</text>')
    for i,(head,body,fill) in enumerate(layers):
        y=115+i*82; svg.append(f'<rect x="160" y="{y}" width="1220" height="60" rx="10" fill="{fill}" stroke="#AEB8C5"/>')
        svg.append(f'<text x="188" y="{y+23}" class="layer">{escape(head)}</text>')
        svg.append(f'<text x="188" y="{y+45}" class="body">{escape(body)}</text>')
        if i < len(layers)-1: svg.append(f'<path d="M770 {y+60} L770 {y+82}" stroke="#6C778A" stroke-width="2" marker-end="url(#arrow)"/>')
    svg.append('<path d="M1400 690 C1500 690 1510 120 1380 120" fill="none" stroke="#0B7D77" stroke-width="2" stroke-dasharray="5,5" marker-end="url(#arrow)"/>')
    svg.append('<text x="1220" y="410" class="small" transform="rotate(-82 1220 410)">feedback / reassessment</text>')
    for i,label in enumerate(["SECURITY","GOVERNANCE","LINEAGE","OBSERVABILITY","FINOPS"]):
        x=1400+i*34; svg.append(f'<rect x="{x}" y="115" width="25" height="574" rx="8" fill="#303744"/>'); svg.append(f'<text x="{x+13}" y="410" fill="#fff" font-size="8" font-family="Arial" transform="rotate(-90 {x+13} 410)" text-anchor="middle">{label}</text>')
    svg.append('<rect x="160" y="725" width="1220" height="48" rx="8" fill="#F5F7FA" stroke="#0B7D77"/>')
    svg.append('<text x="188" y="754" class="body"><tspan font-weight="700">Core distinction:</tspan> External observation ≠ enterprise truth ≠ signal ≠ recommendation ≠ decision ≠ action ≠ outcome</text>')
    svg.append('<text x="40" y="850" class="small">Legend: grey Sources • blue Data • purple Contracts/governance • green Decision intelligence • teal Agentic • orange Execution • solid flow • dashed control • dotted future</text>')
    svg.insert(2, '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6C778A"/></marker></defs>')
    svg.append('</svg>')
    return ''.join(svg)


def write_exports():
    svg = page1_svg(); (OUT / "CPG_Decision_Intelligence_Target_Architecture.svg").write_text(svg, encoding="utf-8")
    try:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
        font_path = "C:/Windows/Fonts/arial.ttf"; bold_path="C:/Windows/Fonts/arialbd.ttf"
        f_title=ImageFont.truetype(bold_path,28); f_sub=ImageFont.truetype(font_path,15); f_head=ImageFont.truetype(bold_path,17); f_body=ImageFont.truetype(font_path,14); f_small=ImageFont.truetype(font_path,12)
        d.text((40,20), "Enterprise CPG AI Discovery & Decision Intelligence", fill="#172033", font=f_title)
        d.text((40,48), "Source-agnostic • Brand-neutral • Market-aware • Product-aware • Closed-loop", fill="#56657A", font=f_sub)
        layers=[("SOURCES / SENSORS","External AI / AEO / GEO sources • retail/search/commerce • enterprise truth","#E7E9ED"),("ACQUISITION","File • API • SFTP • event • ingestion gateway • schema fingerprint","#E7E9ED"),("GOVERNED DATA FOUNDATION","Immutable raw evidence → Bronze → Silver canonical observations → Gold / semantic","#DCEBFA"),("DECISION INTELLIGENCE","Governed metrics → Signals → Diagnosis + enterprise truth → Decision","#DDF2E4"),("AGENTIC / EXPERIENCE","Web app • APIs • assistant • BI • Genie • command centre","#D6F1EF"),("SYSTEMS OF EXECUTION","Workflow • DAM • PIM • CMS / DXP • commerce / retail / ESP","#FBE5C7"),("MEASUREMENT LOOP","Reassessment → comparable outcome → learning → next sensing cycle","#DDF2E4")]
        for i,(head,body,fill) in enumerate(layers):
            y=115+i*82; d.rounded_rectangle((160,y,1380,y+60), radius=10, fill=fill, outline="#AEB8C5", width=1); d.text((188,y+10),head,fill="#172033",font=f_head); d.text((188,y+34),body,fill="#344054",font=f_body)
            if i<len(layers)-1: d.line((770,y+60,770,y+82),fill="#6C778A",width=2)
        for i,label in enumerate(["SECURITY","GOVERNANCE","LINEAGE","OBSERVABILITY","FINOPS"]):
            x=1400+i*34; d.rounded_rectangle((x,115,x+25,689),radius=8,fill="#303744"); d.text((x+3,395),label,fill="white",font=ImageFont.truetype(font_path,8))
        d.rounded_rectangle((160,725,1380,773),radius=8,fill="#F5F7FA",outline="#0B7D77",width=1); d.text((188,741),"Core distinction: External observation ≠ enterprise truth ≠ signal ≠ recommendation ≠ decision ≠ action ≠ outcome",fill="#172033",font=f_body)
        d.text((40,850),"Legend: grey Sources • blue Data • purple Contracts/governance • green Decision intelligence • teal Agentic • orange Execution",fill="#56657A",font=f_small)
        im.save(OUT / "CPG_Decision_Intelligence_Target_Architecture.png")
    except Exception as exc:
        (OUT / "PNG_GENERATION_NOTE.txt").write_text(f"PNG generation unavailable: {exc}\nThe SVG and Draw.io workbook remain the source artifacts.\n", encoding="utf-8")


SUMMARY = '''# Enterprise CPG AI Discovery & Decision Intelligence

## Architecture summary

The target platform is a source-agnostic, configuration-driven closed loop:

**Sense → Understand → Trust → Signal → Diagnose → Decide → Act → Measure**

The architecture keeps seven facts distinct: external observation, enterprise truth, signal, recommendation, decision, action and outcome. Vendor payloads land immutably, are fingerprinted against versioned contracts, and are converted to a common observation envelope plus typed observation families. Contract-aware eligibility prevents unknown or provisional semantics from silently becoming governed business decisions.

The platform is organized into Landing/Raw, Bronze, Silver, Gold and Semantic layers. A control plane holds schema, metric, scope, prompt and signal-rule registries. Deterministic signal computation sits before any LLM. Agents and Genie retrieve governed evidence and explain results, but do not replace the signal engine, truth store, workflow engine or approval process.

## Workbook

The Draw.io workbook contains ten independently readable pages: executive reference, logical platform, schema evolution, signal/decision intelligence, agentic architecture, Kenvue technology mapping, runtime/deployment, end-to-end sequence, security/governance/observability, and scale/multi-tenant model.

## Assumptions

- Target scale is orders of magnitude: hundreds of brands, tens of markets, tens of thousands of products/SKUs, hundreds of thousands of prompts, multiple AI engines, daily/weekly assessments and multi-year history.
- Kenvue technology names are implementation candidates, not ownership recommendations or logical dependencies.
- Data residency, retention, RTO/RPO, availability, accessibility and performance targets remain TBD by the business/platform standard.
- Enterprise truth remains authoritative; external scores are observations and do not prove claim truth or causality.

## Open architectural decisions

1. Select the enterprise contract registry/catalog implementation and steward operating model.
2. Confirm source-provider onboarding standards, API/event authentication and raw retention policy.
3. Choose the approved agent framework and model-routing policy.
4. Define data residency, tenant isolation and market-specific policy requirements.
5. Confirm workflow, DAM/PIM/CMS execution connector priorities.
6. Set measurable NFRs, cost allocation dimensions and DR strategy.

## Top risks and controls

| Risk | Control |
|---|---|
| Vendor schema drift silently changes meaning | Fingerprints, versioned contracts, quarantine, drift events and replay |
| 0–1 metrics are interpreted uniformly when they are not | Metric contracts carry direction, unit, denominator, rank encoding and eligibility |
| LLM invents or overstates a recommendation | Typed evidence packs, citations, safety prompt, validation and deterministic fallback |
| Raw data becomes an unrestricted agent surface | Scoped tools, semantic model, row/market policy and audit tracing |
| Operational state is mixed with analytical facts | PostgreSQL/workflow boundary versus lakehouse data products |
| Outcome comparisons are not like-for-like | Comparable assessment keys include market, language, brand, product, metric, engine and prompt context |

## MVP → enterprise migration path

1. **Foundation:** add contract registries, immutable landing, schema evolution and the canonical observation model.
2. **Scale data:** move durable raw/bronze/silver/gold products to Databricks/Delta with Unity Catalog and dbt quality gates.
3. **Intelligence:** promote signal, truth, decision and outcome services behind stable APIs.
4. **Agentic:** add governed tools, bounded evidence retrieval, Genie as a structured analytics specialist and MLflow/OTel evaluation.
5. **Activation:** add durable workflow and downstream DAM/PIM/CMS/commerce adapters.
6. **Learning:** add reassessment, comparable outcomes, cost attribution and cross-brand intelligence.

## Deliberately out of scope initially

Enterprise-wide identity implementation, replacing existing master-data/truth systems, automatic claim approval, autonomous publishing without policy gates, a per-brand deployment model, a single super-agent, and a claim that vendor observations establish causal business impact.
'''


TECH = '''# Technology Decisions

These are candidate implementation choices for the Kenvue landscape. The logical architecture remains platform-independent and all placements are subject to approved enterprise standards.

| Capability | Why required | Recommended candidate | Alternatives | Boundary |
|---|---|---|---|---|
| Databricks | Scalable engineering, governed data products, analytics and AI/ML | Databricks + Delta Lake | Approved lakehouse equivalent | Do not turn every application transaction into a lakehouse operation |
| dbt | Transparent, versioned analytical transformations and tests | dbt on Databricks | Native SQL/jobs | Not an operational workflow engine |
| Unity Catalog | Catalog, permissions, lineage and data governance | Unity Catalog | Enterprise catalog equivalent | Not a substitute for metric semantics or approval workflow |
| Lakeflow / Jobs | Scheduled and incremental data processing | Lakeflow / Databricks Jobs | Enterprise scheduler | Not durable human workflow state |
| Genie | Governed natural-language analysis of structured curated data | Databricks Genie | Semantic BI assistant | Do not use as signal engine, contract manager, truth store, approval engine or transaction coordinator |
| MLflow 3 | Model/agent evaluation, quality, cost and traceability | MLflow 3 | Enterprise AI evaluation stack | Not the business decision system |
| AKS | Horizontally scalable application and agent runtime | Kubernetes / AKS | Approved container runtime | Not the analytical storage plane |
| Kong | API gateway, routing, policy and edge controls | Kong | Enterprise API gateway | Not workflow persistence |
| Nexus | Container and artifact supply chain | Nexus | Approved artifact registry | Not source data landing |
| PostgreSQL | Operational metadata, API state and transactional records | PostgreSQL | Approved relational OLTP | Not the multi-year analytical lakehouse |
| Redis | Cache and short-lived coordination | Redis | Approved cache | Not system-of-record state |
| Temporal | Durable long-running process orchestration and retries | Temporal | Approved workflow engine | Not an analytical transformation engine |
| Service Bus / Event Hub | Event transport and decoupled acquisition | Azure Service Bus / Event Hub | Approved messaging | Not a substitute for immutable raw storage |
| Azure AI Search / Vector Search | Governed retrieval over evidence and approved content | Azure AI Search / Databricks Vector Search | Approved search/vector layer | Retrieval must preserve source lineage and access policy |
| Key Vault | Secret storage and rotation | Azure Key Vault | Approved secrets manager | Never place secrets in prompts, logs or source files |
| OpenTelemetry | Consistent traces, metrics and logs across services | OpenTelemetry + enterprise monitoring | Equivalent telemetry standard | Must exclude secrets and sensitive payloads |
| Agent framework | Pluggable orchestration of typed tools and bounded context | LangGraph / Semantic Kernel / Databricks agent capability | Other approved framework | Agents assist decisions; they do not become the platform brain |
| App / consumption | Business experience and enterprise intelligence | Web app, APIs, Command Centre / KIIP where appropriate | BI or portal equivalent | KIIP is a candidate channel, not a logical dependency |

## Deliberate boundaries

- **Genie:** use for governed natural-language structured-data analysis. Do not use as the signal engine, schema/metric contract manager, enterprise truth store, business approval engine or general multi-system transaction coordinator.
- **Temporal:** use for durable long-running process orchestration. Do not use as the analytical transformation engine.
- **dbt:** use for transparent/versioned analytical transformation. Do not use as operational workflow storage.
- **Databricks:** use for data engineering, governance, data products, analytics and AI/ML capabilities. Keep application transactions in the operational boundary.
'''


DATA = '''# Canonical Data Model

## Design rules

The model is source-agnostic and configuration-driven. Business dimensions are shared across markets and brands; many-to-many relationship tables handle real CPG relationships. Every canonical fact is traceable to immutable raw evidence and the exact contract, adapter, metric and rule versions used at processing time.

## Core entities and grains

| Entity | Grain | Key fields / purpose |
|---|---|---|
| Enterprise / Market / Language | one governed dimension member | `enterprise_id`, `market_id`, `language_id`; market policy and localization |
| Brand / Sub-brand / Product / SKU | one business entity version | stable business key + surrogate key; effective dates and SCD history |
| Content Asset | one asset version | asset URI, content type, owner reference, effective dates; many-to-many product links |
| Source Provider / Product / Module | one provider capability | provider-independent onboarding metadata |
| Assessment Run | one acquisition/evaluation run in a scope | run key, source, date, market, brand, language, module, provenance |
| Prompt / Prompt Territory | one governed consumer question and territory | prompt key, category/brand/product relationships, version |
| AI Provider / Model / Engine | one model or answer engine version | provider, model, engine and effective dates |
| Schema Contract | one versioned source schema | fingerprint, required/optional fields, types, mappings, compatibility and adapter |
| Metric Contract | one semantic metric version | unit, direction, denominator, rank encoding, eligibility and contract state |
| Source Payload | one immutable file/API payload | payload hash, URI, acquisition timestamp, raw bytes/manifest |
| Source Record | one parsed source row/record | payload ID, row number, raw record hash and quarantine state |
| Observation | one canonical measurement at its natural grain | assessment run, source, prompt/claim/product/engine context, value and lineage |
| Signal | one persisted rule finding | rule/version, metric, scope, status, severity, materiality and explanation |
| Diagnosis / Truth Validation | one finding assessment | state, evidence references, owner, limitation and timestamps |
| Decision | one human/agent-reviewed decision | decision state, rationale, approver, linked signals and truth |
| Intervention | one approved or pending action | action, owner, downstream connector, state, linked signals |
| Outcome | one comparable before/after assessment result | baseline/post run, comparable key, delta, confidence and limitation |

## Canonical observation envelope

`observation_id`, `assessment_run_id`, `source_provider_id`, `source_contract_id`, `source_schema_version`, `adapter_version`, `metric_contract_id`, `metric_contract_version`, `market_id`, `brand_id`, `product_id` (optional), `language_id`, `assessment_timestamp`, `prompt_id` (optional), `claim_id` (optional), `ai_provider_id` (optional), `ai_model_id` (optional), `engine_id` (optional), `source_payload_id`, `source_record_id`, `source_file`, `source_row_number`, `payload_hash`, `record_hash`, `raw_value`, `canonical_value`, `unit`, `direction`, `contract_state`, `eligibility_state`, `ingested_at`.

Typed families should retain domain meaning rather than collapsing everything into one untyped EAV table: visibility/rank observations, answer/claim assessments, citation observations, readiness factors, competitive rankings/scorecards, and outcome measurements.

## Relationships and lineage

- One prompt can belong to many categories, products and brands; use bridge tables.
- One source payload produces many source records; one source record can produce one or more canonical observations.
- One signal links to many observations through a signal-evidence bridge.
- One intervention can address many signals; one signal can have many interventions over time.
- An outcome links to baseline and post assessments through a comparable-assessment bridge and stores the comparison contract/version.
- Assistant responses store intent, bounded context, evidence IDs, validation result, model, latency and fallback status without secrets.

## History and versioning

Use surrogate keys plus effective dating/SCD2 for governed dimensions and contracts. Never overwrite a schema or metric contract that was used by an historical run. Replay selects the historical contract and adapter versions. Facts are append-oriented and corrections are explicit adjustment records.

## Governance states

- `GOVERNED`: verified contract semantics and required truth/eligibility conditions are met.
- `EXPERIMENTAL`: provisional semantics; visible with limitations and not eligible for unrestricted governed action.
- `BLOCKED`: unresolved or unsafe semantics; persisted for transparency but cannot create/approve intervention.
'''


def main():
    (OUT / "CPG_Decision_Intelligence_Target_Architecture.md").write_text(SUMMARY, encoding="utf-8")
    (OUT / "TECHNOLOGY_DECISIONS.md").write_text(TECH, encoding="utf-8")
    (OUT / "DATA_MODEL.md").write_text(DATA, encoding="utf-8")
    write_drawio(); write_exports()
    print(f"Generated architecture artifacts in {OUT}")


if __name__ == "__main__":
    main()
