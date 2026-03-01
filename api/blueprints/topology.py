"""
api/blueprints/topology.py
Blueprint de mapeamento de topologia L2/L3.

Endpoints:
    GET  /topology/              — página principal (KPIs + tabela de nós)
    GET  /topology/nodes         — JSON com nós filtrados
    GET  /topology/vlans         — visão agrupada por VLAN
    GET  /topology/arp           — entradas ARP brutas
    GET  /topology/lldp          — vizinhos LLDP
    POST /topology/scan          — dispara varredura de topologia
    POST /topology/authorize     — marca nó como autorizado
    GET  /topology/graph-data    — JSON para visualização D3.js/Cytoscape
"""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from api.http_utils import wants_json
from core.repositories.topology_repository import (
    count_distinct_vlans,
    count_nodes_by_customer,
    get_node_by_mac,
    list_arp_entries,
    list_lldp_entries,
    list_mac_entries,
    list_nodes,
    list_nodes_by_vlan,
    set_node_authorized,
)
from core.services.topology_service import (
    get_topology_overview,
    run_topology_scan,
)

topology_bp = Blueprint("topology", __name__)


# ── Helpers ──────────────────────────────────────────


def _safe_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── Rotas ────────────────────────────────────────────


@topology_bp.get("/")
def topology_home():
    """Página principal de topologia: KPIs + tabela de nós."""
    customer = request.args.get("customer")
    vlan_id = _safe_int(request.args.get("vlan_id"))

    nodes = list_nodes(customer_id=customer, vlan_id=vlan_id)

    # KPIs simples
    kpis = {
        "total_nodes": len(nodes),
        "total_vlans": count_distinct_vlans(customer) if customer else 0,
    }

    if wants_json(request):
        return jsonify({"kpis": kpis, "nodes": nodes})

    return render_template(
        "topology.html",
        nodes=nodes,
        kpis=kpis,
        customer=customer or "",
        vlan_id=vlan_id,
    )


@topology_bp.get("/nodes")
def topology_nodes_json():
    """Retorna nós de topologia em JSON (API pura)."""
    customer = request.args.get("customer")
    vlan_id = _safe_int(request.args.get("vlan_id"))
    nodes = list_nodes(customer_id=customer, vlan_id=vlan_id)
    return jsonify({"nodes": nodes, "total": len(nodes)})


@topology_bp.get("/vlans")
def topology_vlans():
    """Visão agrupada por VLAN."""
    customer = request.args.get("customer")

    if not customer:
        if wants_json(request):
            return jsonify({"error": "Parâmetro 'customer' obrigatório."}), 400
        flash("Selecione um customer para visualizar VLANs.", "warning")
        return redirect(url_for("topology.topology_home"))

    vlan_groups = list_nodes_by_vlan(customer)

    if wants_json(request):
        return jsonify({"customer": customer, "vlans": vlan_groups})

    return render_template(
        "topology_vlans.html",
        customer=customer,
        vlan_groups=vlan_groups,
    )


@topology_bp.get("/arp")
def topology_arp():
    """Entradas ARP brutas."""
    customer = request.args.get("customer")
    device_id = request.args.get("device_id")
    entries = list_arp_entries(customer_id=customer, device_id=device_id)

    if wants_json(request):
        return jsonify({"arp_entries": entries, "total": len(entries)})

    return render_template(
        "topology.html",
        nodes=entries,
        kpis={"total_nodes": len(entries), "total_vlans": 0},
        customer=customer or "",
        vlan_id=None,
        view_mode="arp",
    )


@topology_bp.get("/lldp")
def topology_lldp():
    """Vizinhos LLDP."""
    customer = request.args.get("customer")
    device_id = request.args.get("device_id")
    entries = list_lldp_entries(customer_id=customer, device_id=device_id)

    if wants_json(request):
        return jsonify({"lldp_entries": entries, "total": len(entries)})

    return render_template(
        "topology.html",
        nodes=entries,
        kpis={"total_nodes": len(entries), "total_vlans": 0},
        customer=customer or "",
        vlan_id=None,
        view_mode="lldp",
    )


@topology_bp.post("/scan")
def topology_scan():
    """Dispara varredura de topologia."""
    customer = request.form.get("customer") or request.json.get("customer") if request.is_json else request.form.get("customer")

    try:
        summary = run_topology_scan(customer_filter=customer or None)
    except Exception as exc:
        if wants_json(request):
            return jsonify({"error": str(exc)}), 500
        flash(f"Erro na varredura: {exc}", "danger")
        return redirect(url_for("topology.topology_home"))

    if wants_json(request):
        return jsonify(summary)

    flash(
        f"Varredura concluída: {summary['devices_scanned']} device(s), "
        f"{summary['nodes_discovered']} nó(s), {summary['drifts']} drift(s).",
        "success",
    )
    return redirect(url_for("topology.topology_home", customer=customer or ""))


@topology_bp.post("/authorize")
def topology_authorize():
    """Marca/desmarca um nó como autorizado."""
    customer = request.form.get("customer_id", "")
    mac = request.form.get("mac_address", "")
    authorize = request.form.get("authorized", "1") == "1"

    if not customer or not mac:
        if wants_json(request):
            return jsonify({"error": "customer_id e mac_address obrigatórios."}), 400
        flash("Parâmetros insuficientes.", "warning")
        return redirect(url_for("topology.topology_home"))

    set_node_authorized(customer, mac, authorize)

    if wants_json(request):
        return jsonify({"ok": True, "mac_address": mac, "authorized": authorize})

    flash(
        f"Nó {mac} {'autorizado' if authorize else 'desautorizado'}.",
        "success",
    )
    return redirect(url_for("topology.topology_home", customer=customer))


@topology_bp.get("/graph-data")
def topology_graph_data():
    """
    JSON com nós e arestas para rendering D3.js / Cytoscape.

    Formato:
        {
            "nodes": [{"id": mac, "label": ip, "vlan": 10, ...}],
            "edges": [{"source": mac_a, "target": mac_b, "type": "lldp"}]
        }
    """
    customer = request.args.get("customer")
    if not customer:
        return jsonify({"error": "Parâmetro 'customer' obrigatório."}), 400

    nodes_raw = list_nodes(customer_id=customer)
    lldp_raw = list_lldp_entries(customer_id=customer)

    # Montar nós
    graph_nodes = []
    for n in nodes_raw:
        graph_nodes.append({
            "id": n["mac_address"],
            "label": n.get("ip_address") or n["mac_address"],
            "vlan": n.get("vlan_id"),
            "vendor": n.get("vendor_oui", ""),
            "authorized": bool(n.get("authorized")),
            "switch_port": n.get("switch_port"),
        })

    # Montar arestas a partir de LLDP
    graph_edges = []
    for entry in lldp_raw:
        if entry.get("remote_mac"):
            graph_edges.append({
                "source": entry.get("local_port", ""),
                "target": entry["remote_mac"],
                "type": "lldp",
                "remote_device": entry.get("remote_device", ""),
            })

    return jsonify({
        "nodes": graph_nodes,
        "edges": graph_edges,
        "total_nodes": len(graph_nodes),
        "total_edges": len(graph_edges),
    })
