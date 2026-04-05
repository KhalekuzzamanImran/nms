import React, { useEffect, useState } from "react";
import laptopImage from "./assets/laptop.svg";
import routerImage from "./assets/router.svg";
import switchImage from "./assets/switch.svg";

const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const TOPOLOGY_API_URL = `${API_BASE_URL}/api/topology/`;
const HOST_METRICS_API_URL = `${API_BASE_URL}/api/host-metrics/`;

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

function formatPercent(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    return `${Number(value).toFixed(2)}%`;
}

function formatMegabytes(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    const mb = Number(value);
    if (mb >= 1024) {
        return `${(mb / 1024).toFixed(mb >= 10240 ? 0 : 1)} GB`;
    }
    return `${mb.toFixed(0)} MB`;
}

function formatBytes(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let amount = Number(value);
    let unitIndex = 0;

    while (amount >= 1024 && unitIndex < units.length - 1) {
        amount /= 1024;
        unitIndex += 1;
    }

    const precision = amount >= 100 ? 0 : amount >= 10 ? 1 : 2;
    return `${amount.toFixed(precision)} ${units[unitIndex]}`;
}

function InfoTile({ label, value }) {
    return (
        <div className="info-tile">
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}

function DiagnosticMessage({ text }) {
    if (!text) return null;
    return <div className="diagnostic-message">{text}</div>;
}

function HostMetricsPanel({ data }) {
    const metrics = data?.host_metrics;
    const cpu = metrics?.cpu || {};
    const memory = metrics?.memory || {};
    const processes = metrics?.processes || {};
    const wifi = metrics?.wifi || null;
    const gpu = metrics?.gpu || null;
    const disks = Array.isArray(metrics?.disk) ? metrics.disk : [];
    const diskError = metrics?.disk_error || null;
    const wifiError = metrics?.wifi_error || null;
    const gpuError = metrics?.gpu_error || null;

    return (
        <section className="metrics-section">
            <div className="section-heading">
                <div>
                    <h2>Host Metrics</h2>
                    <p>Dedicated laptop telemetry from `/api/host-metrics/`</p>
                </div>
                <span className={`pill ${data?.status === "up" ? "pill-green" : "pill-red"}`}>
                    {data?.status || "-"}
                </span>
            </div>

            <div className="metrics-grid">
                <div className="card">
                    <div className="card-title-row">
                        <h3>CPU</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile
                            label="Usage"
                            value={formatPercent(cpu.usage_percent)}
                        />
                        <InfoTile
                            label="Load 1m"
                            value={cpu.load_average?.["1m"] ?? "-"}
                        />
                        <InfoTile
                            label="Load 5m"
                            value={cpu.load_average?.["5m"] ?? "-"}
                        />
                        <InfoTile
                            label="Load 15m"
                            value={cpu.load_average?.["15m"] ?? "-"}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>Memory</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile
                            label="Used"
                            value={formatMegabytes(memory.used_mb)}
                        />
                        <InfoTile
                            label="Available"
                            value={formatMegabytes(memory.available_mb)}
                        />
                        <InfoTile
                            label="Total"
                            value={formatMegabytes(memory.total_mb)}
                        />
                        <InfoTile
                            label="Usage"
                            value={formatPercent(memory.usage_percent)}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>Processes</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile
                            label="Count"
                            value={processes.count ?? "-"}
                        />
                        <InfoTile
                            label="Swap Used"
                            value={formatMegabytes(memory.swap_used_mb)}
                        />
                        <InfoTile
                            label="Swap Total"
                            value={formatMegabytes(memory.swap_total_mb)}
                        />
                        <InfoTile
                            label="Swap Usage"
                            value={formatPercent(memory.swap_usage_percent)}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>Wireless</h3>
                    </div>
                    <DiagnosticMessage text={wifiError} />
                    <div className="metrics-list">
                        <InfoTile
                            label="Interface"
                            value={wifi?.iface || "-"}
                        />
                        <InfoTile
                            label="SSID"
                            value={wifi?.ssid || "-"}
                        />
                        <InfoTile
                            label="Signal"
                            value={
                                wifi?.signal_dbm != null
                                    ? `${wifi.signal_dbm} dBm`
                                    : "-"
                            }
                        />
                        <InfoTile
                            label="TX Rate"
                            value={
                                wifi?.tx_bitrate_mbps != null
                                    ? `${wifi.tx_bitrate_mbps} Mbps`
                                    : "-"
                            }
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>GPU</h3>
                    </div>
                    <DiagnosticMessage text={gpuError} />
                    <div className="metrics-list">
                        <InfoTile
                            label="Utilization"
                            value={
                                gpu?.util_percent != null
                                    ? `${gpu.util_percent}%`
                                    : gpu?.status || "-"
                            }
                        />
                        <InfoTile
                            label="Memory Used"
                            value={formatMegabytes(gpu?.memory_used_mb)}
                        />
                        <InfoTile
                            label="Memory Total"
                            value={formatMegabytes(gpu?.memory_total_mb)}
                        />
                        <InfoTile
                            label="Temperature"
                            value={gpu?.temp_c != null ? `${gpu.temp_c} C` : "-"}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>Disk</h3>
                    </div>
                    <DiagnosticMessage text={diskError} />
                    <div className="disk-list">
                        {disks.length ? (
                            disks.map((disk) => (
                                <div className="disk-row" key={disk.index}>
                                    <div>
                                        <strong>{disk.mount || `Disk ${disk.index}`}</strong>
                                        <span className="disk-type">
                                            {disk.storage_type || "storage"}
                                        </span>
                                        <span>
                                            {formatBytes(disk.used_bytes)} /{" "}
                                            {formatBytes(disk.total_bytes)}
                                        </span>
                                    </div>
                                    <strong>
                                        {formatPercent(disk.usage_percent)}
                                    </strong>
                                </div>
                            ))
                        ) : (
                            <div className="empty-state">No disk metrics available.</div>
                        )}
                    </div>
                </div>
            </div>
        </section>
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
    const [topologyData, setTopologyData] = useState(null);
    const [hostMetricsData, setHostMetricsData] = useState(null);
    const [loading, setLoading] = useState(true);

    async function load() {
        try {
            const [topologyRes, hostMetricsRes] = await Promise.all([
                fetch(TOPOLOGY_API_URL),
                fetch(HOST_METRICS_API_URL),
            ]);
            const [topologyJson, hostMetricsJson] = await Promise.all([
                topologyRes.json(),
                hostMetricsRes.json(),
            ]);
            setTopologyData(topologyJson);
            setHostMetricsData(hostMetricsJson);
        } catch (e) {
            setTopologyData(null);
            setHostMetricsData(null);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        load();
        const timer = setInterval(load, 5000);
        return () => clearInterval(timer);
    }, []);

    const nodes = topologyData?.nodes || {};
    const links = topologyData?.links || {};
    const laptopNode = hostMetricsData?.node || nodes.laptop;

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
                <DeviceCard title="Ubuntu Laptop" data={laptopNode} />
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

            <HostMetricsPanel data={laptopNode} />
        </div>
    );
}
