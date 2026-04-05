import React, { useEffect, useState } from "react";
import laptopImage from "./assets/laptop.svg";
import routerImage from "./assets/router.svg";
import switchImage from "./assets/switch.svg";

const API_URL = "http://127.0.0.1:8000/api/topology/";

function DeviceCard({ title, data }) {
    const online = data?.status === "up";
    return (
        <div className={`card device ${online ? "online" : "offline"}`}>
            <div className="card-title-row">
                <h2>{title}</h2>
                <span className={`pill ${online ? "pill-green" : "pill-red"}`}>
                    {data?.status || "-"}
                </span>
            </div>
            <div>
                <strong>Name:</strong> {data?.name || "-"}
            </div>
            <div>
                <strong>IP:</strong> {data?.ip || "-"}
            </div>
            <div>
                <strong>Uptime:</strong> {data?.uptime || "-"}
            </div>
            <div>
                <strong>Description:</strong> {data?.description || "-"}
            </div>
            {data?.error ? (
                <div>
                    <strong>Error:</strong> {data.error}
                </div>
            ) : null}
        </div>
    );
}

function LinkCard({ title, link, rightLabel = "Peer port" }) {
    const up = link?.status === "up";
    const left = link?.router_side || link?.switch_side || {};
    const right =
        link?.switch_side && link?.router_side ? link.switch_side : null;

    return (
        <div className="card">
            <div className="card-title-row">
                <h3>{title}</h3>
                <span className={`pill ${up ? "pill-green" : "pill-red"}`}>
                    {link?.status || "-"}
                </span>
            </div>

            {"discovered_port_index" in (link || {}) ? (
                <div>
                    <strong>Discovery:</strong> {link.discovery_method || "-"}
                </div>
            ) : null}

            <div>
                <strong>Primary port:</strong> {left.port_name || "-"} (index{" "}
                {left.port_index ?? "-"})
            </div>
            <div>
                <strong>Admin:</strong> {left.admin_status_label || "-"}
            </div>
            <div>
                <strong>Oper:</strong> {left.oper_status_label || "-"}
            </div>
            <div>
                <strong>Speed:</strong> {left.speed_mbps ?? "-"} Mbps
            </div>
            <div>
                <strong>Traffic:</strong> In {left.in_octets ?? "-"} / Out{" "}
                {left.out_octets ?? "-"}
            </div>
            <div>
                <strong>Errors:</strong> In {left.in_errors ?? "-"} / Out{" "}
                {left.out_errors ?? "-"}
            </div>
            <div>
                <strong>Last change:</strong> {left.last_change || "-"}
            </div>

            {right ? (
                <>
                    <hr />
                    <div>
                        <strong>{rightLabel}:</strong> {right.port_name || "-"}{" "}
                        (index {right.port_index ?? "-"})
                    </div>
                    <div>
                        <strong>Peer admin:</strong>{" "}
                        {right.admin_status_label || "-"}
                    </div>
                    <div>
                        <strong>Peer oper:</strong>{" "}
                        {right.oper_status_label || "-"}
                    </div>
                    <div>
                        <strong>Peer speed:</strong> {right.speed_mbps ?? "-"}{" "}
                        Mbps
                    </div>
                    <div>
                        <strong>Peer traffic:</strong> In{" "}
                        {right.in_octets ?? "-"} / Out {right.out_octets ?? "-"}
                    </div>
                    <div>
                        <strong>Peer errors:</strong> In{" "}
                        {right.in_errors ?? "-"} / Out {right.out_errors ?? "-"}
                    </div>
                    <div>
                        <strong>Peer last change:</strong>{" "}
                        {right.last_change || "-"}
                    </div>
                </>
            ) : null}
        </div>
    );
}

function formatBandwidth(mbps) {
    if (mbps == null || Number.isNaN(Number(mbps))) return "-";
    const value = Number(mbps);
    if (value >= 1000)
        return `${(value / 1000).toFixed(value % 1000 === 0 ? 1 : 2)} Gbps`;
    return `${value} Mbps`;
}

function getPrimarySide(link) {
    return link?.switch_side || link?.router_side || null;
}

function getLinkSpeed(link) {
    return (
        link?.switch_side?.speed_mbps ?? link?.router_side?.speed_mbps ?? null
    );
}

function DeviceNode({ title, imageSrc, imageAlt, accent = "mint" }) {
    return (
        <article className="topology-device">
            <div className={`flow-icon-shell-${accent}`}>
                <img
                    className="flow-icon-image"
                    src={imageSrc}
                    alt={imageAlt}
                />
            </div>
            <h4>{title}</h4>
        </article>
    );
}

function StatusInfoBox({ title, status, metrics = [] }) {
    const online = status === "up";

    return (
        <aside className="topology-status-box">
            <h4>{title}</h4>
            <div
                className={`flow-chip ${online ? "flow-chip-up" : "flow-chip-down"}`}
            >
                <span className="flow-chip-dot"></span>
                {online ? "Active" : "Offline"}
            </div>
            <div className="topology-status-metrics">
                {metrics.map((metric) => (
                    <div key={metric.label} className="flow-node-metric">
                        <span>{metric.label}</span>
                        <strong>{metric.value}</strong>
                    </div>
                ))}
            </div>
        </aside>
    );
}

function TopologyMap({ nodes, links }) {
    const rsUp = links?.router_to_switch?.status === "up";
    const slUp = links?.switch_to_laptop?.status === "up";
    const routerSwitchSide = getPrimarySide(links?.router_to_switch);
    const switchLaptopSide = getPrimarySide(links?.switch_to_laptop);

    return (
        <section className="traffic-flow-card">
            <div className="traffic-flow-header">
                <div className="traffic-flow-heading">
                    <div className="traffic-flow-logo">NF</div>
                    <div>
                        <h3>Topology Map</h3>
                        <p>Router, switch, and laptop connection path</p>
                    </div>
                </div>
            </div>

            <div className="topology-diagram">
                <StatusInfoBox
                    title="Router"
                    status={nodes?.router?.status}
                    metrics={[
                        { label: "Name", value: nodes?.router?.name || "-" },
                        {
                            label: "Port",
                            value: routerSwitchSide?.port_name || "-",
                        },
                        {
                            label: "Uplink",
                            value: formatBandwidth(
                                getLinkSpeed(links?.router_to_switch),
                            ),
                        },
                    ]}
                />

                <DeviceNode
                    title="Router"
                    imageSrc={routerImage}
                    imageAlt="Router"
                    accent="blue"
                />

                <div className="topology-link topology-link-horizontal">
                    <div
                        className={`flow-connector ${rsUp ? "flow-connector-up" : "flow-connector-down"}`}
                    ></div>
                    <div className="flow-connector-meta topology-link-label">
                        <span>Router to Switch</span>
                        <strong>
                            {formatBandwidth(
                                getLinkSpeed(links?.router_to_switch),
                            )}
                        </strong>
                    </div>
                </div>

                <DeviceNode
                    title="Switch"
                    imageSrc={switchImage}
                    imageAlt="Switch"
                    accent="mint"
                />

                <StatusInfoBox
                    title="Switch"
                    status={nodes?.switch?.status}
                    metrics={[
                        {
                            label: "Name",
                            value: nodes?.switch?.name || "-",
                        },
                        {
                            label: "Port",
                            value:
                                switchLaptopSide?.port_name ||
                                routerSwitchSide?.port_name ||
                                "-",
                        },
                        { label: "Address", value: nodes?.switch?.ip || "-" },
                    ]}
                />

                <div className="topology-link topology-link-vertical">
                    <div
                        className={`flow-branch-line ${slUp ? "flow-connector-up" : "flow-connector-down"}`}
                    ></div>
                    <div className="flow-connector-meta flow-connector-meta-vertical">
                        <span>Switch to PC</span>
                        <strong>
                            {formatBandwidth(
                                getLinkSpeed(links?.switch_to_laptop),
                            )}
                        </strong>
                    </div>
                </div>

                <DeviceNode
                    title="Laptop"
                    imageSrc={laptopImage}
                    imageAlt="Laptop"
                    accent="cyan"
                />

                <StatusInfoBox
                    title="Laptop"
                    status={nodes?.laptop?.status}
                    metrics={[
                        {
                            label: "Name",
                            value: nodes?.laptop?.name || "-",
                        },
                        { label: "Address", value: nodes?.laptop?.ip || "-" },
                        {
                            label: "Link",
                            value: formatBandwidth(
                                getLinkSpeed(links?.switch_to_laptop),
                            ),
                        },
                    ]}
                />
            </div>
        </section>
    );
}

export default function App() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    async function load() {
        try {
            const res = await fetch(API_URL);
            const json = await res.json();
            setData(json);
        } catch (e) {
            setData(null);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        load();
        const timer = setInterval(load, 5000);
        return () => clearInterval(timer);
    }, []);

    const nodes = data?.nodes || {};
    const links = data?.links || {};

    return (
        <div className="page">
            <h1>SNMP Topology Dashboard</h1>
            <p className="sub">
                Router, switch, and Ubuntu laptop with dynamic switch-port
                discovery
            </p>

            {loading && <div>Loading...</div>}

            <TopologyMap nodes={nodes} links={links} />

            <div className="device-grid">
                <DeviceCard title="Router" data={nodes.router} />
                <DeviceCard title="Switch" data={nodes.switch} />
                <DeviceCard title="Ubuntu Laptop" data={nodes.laptop} />
            </div>

            <div className="link-grid">
                <LinkCard
                    title="Router to Switch"
                    link={links.router_to_switch}
                    rightLabel="Peer port"
                />
                <LinkCard
                    title="Switch to Laptop"
                    link={links.switch_to_laptop}
                />
            </div>
        </div>
    );
}
