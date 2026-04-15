import React, { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import "xterm/css/xterm.css";
import laptopImage from "./assets/laptop.svg";
import routerSvgTemplate from "./assets/router.svg?raw";
import serverImage from "./assets/server1.svg";
import switchImage from "./assets/switch.svg";

const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const TOPOLOGY_API_URL = `${API_BASE_URL}/api/topology/`;
const HISTORY_CHARTS_API_URL = `${API_BASE_URL}/api/history/charts/`;
const SSH_SESSION_API_URL = `${API_BASE_URL}/api/ssh/session/`;

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

function formatLatency(value) {
    if (value == null || Number.isNaN(Number(value))) return "-";
    return `${Number(value).toFixed(2)} ms`;
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

function RouterPortsCard({ data }) {
    const router = data?.router;
    const physicalPorts = data?.physical_ports;
    const ports = Array.isArray(physicalPorts?.ports)
        ? physicalPorts.ports
        : [];
    const upPorts = ports.filter((port) => port.oper_status === 1);
    const downPorts = ports.filter((port) => port.oper_status !== 1);

    function formatPortList(portList) {
        if (!portList.length) return "-";
        return portList
            .map((port) => `${port.port_name} (#${port.port_index})`)
            .join(", ");
    }

    return null;
}

function buildWebSocketUrl(path, token) {
    const base = API_BASE_URL.replace(/^http/, "ws").replace(/\/$/, "");
    return `${base}${path}?token=${encodeURIComponent(token)}`;
}

function buildStatusSocketUrl() {
    return `${API_BASE_URL.replace(/^http/, "ws").replace(/\/$/, "")}/ws/status/`;
}

function SshTerminalModal({ device, onClose }) {
    const terminalHostRef = useRef(null);
    const terminalRef = useRef(null);
    const socketRef = useRef(null);
    const plainOutputRef = useRef(null);
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [connecting, setConnecting] = useState(false);
    const [error, setError] = useState("");
    const [terminalMode, setTerminalMode] = useState("loading");
    const [plainOutput, setPlainOutput] = useState("");
    const [plainInput, setPlainInput] = useState("");
    const [isConnected, setIsConnected] = useState(false);

    function appendOutput(text) {
        if (terminalRef.current) {
            terminalRef.current.write(text);
            terminalRef.current.scrollToBottom();
            return;
        }
        setPlainOutput((current) => `${current}${text}`);
    }

    function resetOutput(text) {
        if (terminalRef.current) {
            terminalRef.current.clear();
            terminalRef.current.write(text);
            terminalRef.current.scrollToBottom();
            return;
        }
        setPlainOutput(text);
    }

    useEffect(() => {
        try {
            if (terminalHostRef.current && !terminalRef.current) {
                const terminal = new Terminal({
                    cursorBlink: true,
                    fontSize: 13,
                    rows: 18,
                    cols: 80,
                    scrollback: 5000,
                    theme: {
                        background: "#081120",
                        foreground: "#e2e8f0",
                    },
                });
                terminal.open(terminalHostRef.current);
                terminal.writeln(
                    `SSH target: ${device.title} (${device.ip || "unknown"})`,
                );
                terminal.writeln("Enter credentials, then click Connect.");
                terminal.scrollToBottom();
                terminal.focus();
                terminalRef.current = terminal;
                setTerminalMode("xterm");
            }
        } catch (terminalError) {
            setTerminalMode("plain");
            setPlainOutput(
                `SSH target: ${device.title} (${device.ip || "unknown"})\nEnter credentials, then click Connect.\n\nxterm could not be initialized, so plain terminal mode is being used.\n`,
            );
            setError(`${terminalError.message}. Using plain terminal mode.`);
        }

        return () => {
            if (socketRef.current) {
                socketRef.current.close();
                socketRef.current = null;
            }
            if (terminalRef.current) {
                terminalRef.current.dispose();
                terminalRef.current = null;
            }
        };
    }, [device]);

    async function handleConnect(event) {
        event.preventDefault();
        setConnecting(true);
        setError("");

        try {
            const response = await fetch(SSH_SESSION_API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    device: device.id,
                    username,
                    password,
                }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(
                    payload.detail || "Unable to create SSH session.",
                );
            }

            resetOutput(
                `Connecting to ${payload.device.name} (${payload.device.host})...\r\n`,
            );

            const socket = new WebSocket(
                buildWebSocketUrl(payload.ws_path, payload.token),
            );
            socketRef.current = socket;

            socket.onopen = () => {
                setIsConnected(true);
                appendOutput("SSH connected.\r\n");
                if (terminalRef.current) {
                    terminalRef.current.focus();
                    terminalRef.current.onData((data) => {
                        if (socket.readyState === WebSocket.OPEN) {
                            socket.send(data);
                        }
                    });
                }
            };

            socket.onmessage = (message) => {
                appendOutput(message.data);
            };

            socket.onerror = () => {
                setError("SSH websocket error.");
            };

            socket.onclose = () => {
                setIsConnected(false);
                appendOutput("\r\nConnection closed.\r\n");
            };
        } catch (connectError) {
            setError(connectError.message);
        } finally {
            setConnecting(false);
        }
    }

    useEffect(() => {
        if (plainOutputRef.current) {
            plainOutputRef.current.scrollTop =
                plainOutputRef.current.scrollHeight;
        }
    }, [plainOutput]);

    function handlePlainInputSubmit(event) {
        event.preventDefault();
        if (
            !plainInput ||
            !socketRef.current ||
            socketRef.current.readyState !== WebSocket.OPEN
        ) {
            return;
        }
        appendOutput(`$ ${plainInput}\r\n`);
        socketRef.current.send(`${plainInput}\r`);
        setPlainInput("");
    }

    function handlePlainInputKeyDown(event) {
        if (
            event.key === "c" &&
            (event.ctrlKey || event.metaKey) &&
            socketRef.current &&
            socketRef.current.readyState === WebSocket.OPEN
        ) {
            event.preventDefault();
            socketRef.current.send("\u0003");
        }
    }

    return (
        <div className="ssh-modal-backdrop" onClick={onClose}>
            <div
                className="ssh-modal"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="ssh-modal-header">
                    <div>
                        <h2>SSH Terminal</h2>
                        <p>
                            {device.title} {device.ip ? `(${device.ip})` : ""}
                        </p>
                    </div>
                    <button
                        type="button"
                        className="ssh-close-button"
                        onClick={onClose}
                    >
                        Close
                    </button>
                </div>

                <form className="ssh-credential-form" onSubmit={handleConnect}>
                    <input
                        type="text"
                        placeholder="Username"
                        value={username}
                        onChange={(event) => setUsername(event.target.value)}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                    />
                    <button type="submit" disabled={connecting}>
                        {connecting ? "Connecting..." : "Connect"}
                    </button>
                </form>

                {error ? <div className="ssh-error">{error}</div> : null}

                {terminalMode === "xterm" ? (
                    <div
                        ref={terminalHostRef}
                        className="ssh-terminal-host"
                        onClick={() => terminalRef.current?.focus()}
                    />
                ) : (
                    <div className="ssh-plain-terminal">
                        <pre ref={plainOutputRef} className="ssh-plain-output">
                            {plainOutput}
                        </pre>
                        <form
                            className="ssh-plain-input-form"
                            onSubmit={handlePlainInputSubmit}
                        >
                            <input
                                type="text"
                                className="ssh-plain-command-input"
                                placeholder={
                                    isConnected
                                        ? "Type a command and press Enter. Press Ctrl+C to interrupt."
                                        : "Connect first to start typing commands."
                                }
                                value={plainInput}
                                onChange={(event) =>
                                    setPlainInput(event.target.value)
                                }
                                onKeyDown={handlePlainInputKeyDown}
                                disabled={!isConnected}
                                autoComplete="off"
                                autoCapitalize="off"
                                autoCorrect="off"
                                spellCheck="false"
                            />
                        </form>
                    </div>
                )}
            </div>
        </div>
    );
}

function HostMetricsPanel({
    data,
    title = "Host Metrics",
    description = "Dedicated telemetry",
}) {
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
                    <h2>{title}</h2>
                    <p>{description}</p>
                </div>
                <span
                    className={`pill ${data?.status === "up" ? "pill-green" : "pill-red"}`}
                >
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
                        <InfoTile label="SSID" value={wifi?.ssid || "-"} />
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
                            value={
                                gpu?.temp_c != null ? `${gpu.temp_c} C` : "-"
                            }
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
                                        <strong>
                                            {disk.mount || `Disk ${disk.index}`}
                                        </strong>
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
                            <div className="empty-state">
                                No disk metrics available.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </section>
    );
}

function ServerRealtimeMetricsPanel({ data }) {
    const metrics = data?.host_metrics || {};
    const cpu = metrics.cpu || {};
    const cpuError = metrics.cpu_error || null;
    const memory = metrics.memory || {};
    const memoryError = metrics.memory_error || null;
    const processes = metrics.processes || {};
    const disks = Array.isArray(metrics.disk) ? metrics.disk : [];
    const diskError = metrics.disk_error || null;
    const network = metrics.network || null;
    const networkError = metrics.network_error || null;
    const ping = data?.ping || {};

    return (
        <section className="metrics-section">
            <div className="section-heading">
                <div>
                    <h2>Realtime Server Metrics</h2>
                    <p>Live server telemetry refreshed from SNMP polling.</p>
                </div>
                <span
                    className={`pill ${data?.status === "up" ? "pill-green" : "pill-red"}`}
                >
                    {data?.status || "-"}
                </span>
            </div>

            <div className="metrics-grid">
                <div className="card">
                    <div className="card-title-row">
                        <h3>Server Summary</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile label="Name" value={data?.name || "-"} />
                        <InfoTile label="IP" value={data?.ip || "-"} />
                        <InfoTile label="Uptime" value={data?.uptime || "-"} />
                        <InfoTile
                            label="Processes"
                            value={processes.count ?? "-"}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>CPU & Memory</h3>
                    </div>
                    <DiagnosticMessage text={cpuError || memoryError} />
                    <div className="metrics-list">
                        <InfoTile
                            label="CPU Usage"
                            value={formatPercent(cpu.usage_percent)}
                        />
                        <InfoTile
                            label="Load 1m"
                            value={cpu.load_average?.["1m"] ?? "-"}
                        />
                        <InfoTile
                            label="Memory Used"
                            value={formatMegabytes(memory.used_mb)}
                        />
                        <InfoTile
                            label="Memory Usage"
                            value={formatPercent(memory.usage_percent)}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>Network Health</h3>
                    </div>
                    <DiagnosticMessage text={networkError || ping.error} />
                    <div className="metrics-list">
                        <InfoTile
                            label="Interface"
                            value={network?.iface || "-"}
                        />
                        <InfoTile
                            label="Avg Latency"
                            value={formatLatency(ping.avg_latency_ms)}
                        />
                        <InfoTile
                            label="Packet Loss"
                            value={formatPercent(ping.packet_loss_percent)}
                        />
                        <InfoTile
                            label="Packets Sent"
                            value={ping.sent ?? "-"}
                        />
                        <InfoTile
                            label="Packets Received"
                            value={ping.received ?? "-"}
                        />
                        <InfoTile
                            label="RX Bytes"
                            value={formatBytes(network?.rx_bytes)}
                        />
                        <InfoTile
                            label="TX Bytes"
                            value={formatBytes(network?.tx_bytes)}
                        />
                        <InfoTile
                            label="RX Packets"
                            value={network?.rx_packets ?? "-"}
                        />
                        <InfoTile
                            label="TX Packets"
                            value={network?.tx_packets ?? "-"}
                        />
                    </div>
                </div>

                {/* <div className="card metrics-grid-span-3">
                    <div className="card-title-row">
                        <h3>Disk Usage</h3>
                    </div>
                    <DiagnosticMessage text={diskError} />
                    <div className="disk-list">
                        {disks.length ? (
                            disks.map((disk) => (
                                <div className="disk-row" key={disk.index}>
                                    <div>
                                        <strong>
                                            {disk.mount || `Disk ${disk.index}`}
                                        </strong>
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
                            <div className="empty-state">
                                No disk metrics available.
                            </div>
                        )}
                    </div>
                </div> */}
            </div>
        </section>
    );
}

function formatChartTime(value) {
    try {
        return new Date(value).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "";
    }
}

function HistoryLineChart({ title, seriesByDevice, formatter, yDomain = null }) {
    const colors = {
        router: "#38bdf8",
        switch: "#34d399",
        laptop: "#f59e0b",
        server: "#f472b6",
    };
    const entries = Object.entries(seriesByDevice || {}).filter(([, points]) =>
        Array.isArray(points) && points.length
    );

    const allValues = entries.flatMap(([, points]) =>
        points.map((point) => Number(point.value)).filter((value) => !Number.isNaN(value))
    );
    const minValue = yDomain ? yDomain[0] : allValues.length ? Math.min(...allValues) : 0;
    const maxValue = yDomain ? yDomain[1] : allValues.length ? Math.max(...allValues) : 1;
    const valueSpan = maxValue - minValue || 1;
    const xAxisPoints = entries[0]?.[1] || [];
    const yAxisLabels = Array.from({ length: 5 }, (_, index) => {
        const ratio = 1 - index / 4;
        return minValue + valueSpan * ratio;
    });
    const xAxisLabels = [
        xAxisPoints[0],
        xAxisPoints[Math.max(0, Math.floor((xAxisPoints.length - 1) / 2))],
        xAxisPoints[xAxisPoints.length - 1],
    ].filter(Boolean);

    function buildPath(points) {
        return points
            .map((point, index) => {
                const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 100;
                const normalized = Math.max(
                    0,
                    Math.min(1, (Number(point.value) - minValue) / valueSpan),
                );
                const y = 100 - normalized * 100;
                return `${index === 0 ? "M" : "L"} ${x} ${y}`;
            })
            .join(" ");
    }

    function buildPointPosition(points, index) {
        const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 100;
        const normalized = Math.max(
            0,
            Math.min(1, (Number(points[index].value) - minValue) / valueSpan),
        );
        const y = 100 - normalized * 100;
        return { x, y };
    }

    function buildAreaPath(points) {
        if (!points.length) return "";
        const linePath = buildPath(points);
        const lastX = points.length === 1 ? 0 : 100;
        return `${linePath} L ${lastX} 100 L 0 100 Z`;
    }

    const latestTime = entries[0]?.[1]?.at(-1)?.time;

    return (
        <div className="card chart-card">
            <div className="card-title-row">
                <h3>{title}</h3>
                <span className="chart-subtitle">
                    {latestTime ? `Updated ${formatChartTime(latestTime)}` : "Waiting for data"}
                </span>
            </div>
            {entries.length ? (
                <>
                    <div className="history-chart-shell">
                        <div className="history-y-axis">
                            {yAxisLabels.map((label, index) => (
                                <span key={`${title}-y-${index}`}>
                                    {formatter(label)}
                                </span>
                            ))}
                        </div>
                        <div className="history-chart-main">
                            <svg viewBox="0 0 100 100" className="history-chart">
                                <defs>
                                    {entries.map(([device]) => (
                                        <linearGradient
                                            key={`${device}-gradient`}
                                            id={`${title}-${device}-gradient`}
                                            x1="0"
                                            x2="0"
                                            y1="0"
                                            y2="1"
                                        >
                                            <stop
                                                offset="0%"
                                                stopColor={colors[device] || "#93a4bf"}
                                                stopOpacity="0.32"
                                            />
                                            <stop
                                                offset="100%"
                                                stopColor={colors[device] || "#93a4bf"}
                                                stopOpacity="0.02"
                                            />
                                        </linearGradient>
                                    ))}
                                </defs>
                                {Array.from({ length: 5 }, (_, index) => {
                                    const y = index * 25;
                                    return (
                                        <line
                                            key={`${title}-grid-y-${index}`}
                                            x1="0"
                                            y1={y}
                                            x2="100"
                                            y2={y}
                                            className="history-grid-line"
                                        />
                                    );
                                })}
                                {Array.from({ length: 6 }, (_, index) => {
                                    const x = index * 20;
                                    return (
                                        <line
                                            key={`${title}-grid-x-${index}`}
                                            x1={x}
                                            y1="0"
                                            x2={x}
                                            y2="100"
                                            className="history-grid-line history-grid-line-vertical"
                                        />
                                    );
                                })}
                                {entries.map(([device, points]) => (
                                    <path
                                        key={`${device}-area`}
                                        d={buildAreaPath(points)}
                                        fill={`url(#${title}-${device}-gradient)`}
                                    />
                                ))}
                                {entries.map(([device, points]) => (
                                    <path
                                        key={device}
                                        d={buildPath(points)}
                                        fill="none"
                                        stroke={colors[device] || "#93a4bf"}
                                        strokeWidth="2.4"
                                        vectorEffect="non-scaling-stroke"
                                    />
                                ))}
                                {entries.flatMap(([device, points]) =>
                                    points.map((point, index) => {
                                        const position = buildPointPosition(points, index);
                                        return (
                                            <circle
                                                key={`${device}-point-${index}`}
                                                cx={position.x}
                                                cy={position.y}
                                                r="1.8"
                                                fill={colors[device] || "#93a4bf"}
                                            />
                                        );
                                    }),
                                )}
                            </svg>
                            <div className="history-x-axis">
                                {xAxisLabels.map((point, index) => (
                                    <span key={`${title}-x-${index}`}>
                                        {formatChartTime(point.time)}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="chart-legend">
                        {entries.map(([device, points]) => (
                            <div key={device} className="chart-legend-item">
                                <span
                                    className="chart-legend-dot"
                                    style={{ backgroundColor: colors[device] || "#93a4bf" }}
                                />
                                <strong>{device}</strong>
                                <span>{formatter(points.at(-1)?.value)}</span>
                            </div>
                        ))}
                    </div>
                </>
            ) : (
                <div className="empty-state">No historical data in InfluxDB yet.</div>
            )}
        </div>
    );
}

function HistoricalCharts({ history }) {
    const series = history?.series || {};
    const cpuSeries = {};
    const memorySeries = {};
    const latencySeries = {};

    Object.entries(series).forEach(([device, metrics]) => {
        cpuSeries[device] = metrics.cpu_usage || [];
        memorySeries[device] = metrics.memory_usage || [];
        latencySeries[device] = metrics.latency_ms || [];
    });

    const serverMetrics = series.server || {};
    const serverCpuSeries = { server: cpuSeries.server || [] };
    const serverMemorySeries = { server: memorySeries.server || [] };
    const serverLatencySeries = {
        server: serverMetrics.latency_ms || latencySeries.server || [],
    };
    const serverPacketLossSeries = {
        server: serverMetrics.packet_loss || [],
    };
    const serverProcessSeries = {
        server: serverMetrics.process_count || [],
    };
    const serverDiskUsageSeries = {
        server: serverMetrics.disk_usage || [],
    };
    const serverRxBytesSeries = {
        server: serverMetrics.rx_bytes || [],
    };
    const serverTxBytesSeries = {
        server: serverMetrics.tx_bytes || [],
    };
    const serverMemoryUsedSeries = {
        server: serverMetrics.memory_used_mb || [],
    };

    return (
        <section className="metrics-section">
            <div className="section-heading">
                <div>
                    <h2>Historical Trends</h2>
                    <p>InfluxDB-backed metrics history updated alongside the poller.</p>
                </div>
            </div>
            <div className="history-charts-stack">
                <HistoryLineChart
                    title="CPU Usage By Device"
                    seriesByDevice={cpuSeries}
                    formatter={(value) => formatPercent(value)}
                    yDomain={[0, 100]}
                />
                <HistoryLineChart
                    title="Memory Usage By Device"
                    seriesByDevice={memorySeries}
                    formatter={(value) => formatPercent(value)}
                    yDomain={[0, 100]}
                />
                <HistoryLineChart
                    title="Latency By Device"
                    seriesByDevice={latencySeries}
                    formatter={(value) => formatLatency(value)}
                />
                <HistoryLineChart
                    title="Server CPU Usage"
                    seriesByDevice={serverCpuSeries}
                    formatter={(value) => formatPercent(value)}
                    yDomain={[0, 100]}
                />
                <HistoryLineChart
                    title="Server Memory Usage"
                    seriesByDevice={serverMemorySeries}
                    formatter={(value) => formatPercent(value)}
                    yDomain={[0, 100]}
                />
                <HistoryLineChart
                    title="Server Memory Used"
                    seriesByDevice={serverMemoryUsedSeries}
                    formatter={(value) => formatMegabytes(value)}
                />
                <HistoryLineChart
                    title="Server Latency"
                    seriesByDevice={serverLatencySeries}
                    formatter={(value) => formatLatency(value)}
                />
                <HistoryLineChart
                    title="Server Packet Loss"
                    seriesByDevice={serverPacketLossSeries}
                    formatter={(value) => formatPercent(value)}
                    yDomain={[0, 100]}
                />
                <HistoryLineChart
                    title="Server Process Count"
                    seriesByDevice={serverProcessSeries}
                    formatter={(value) =>
                        value == null || Number.isNaN(Number(value))
                            ? "-"
                            : Math.round(Number(value)).toString()
                    }
                />
                <HistoryLineChart
                    title="Server Disk Usage"
                    seriesByDevice={serverDiskUsageSeries}
                    formatter={(value) => formatPercent(value)}
                    yDomain={[0, 100]}
                />
                <HistoryLineChart
                    title="Server RX Bytes"
                    seriesByDevice={serverRxBytesSeries}
                    formatter={(value) => formatBytes(value)}
                />
                <HistoryLineChart
                    title="Server TX Bytes"
                    seriesByDevice={serverTxBytesSeries}
                    formatter={(value) => formatBytes(value)}
                />
            </div>
        </section>
    );
}

function NetworkDeviceMetricsPanel({
    data,
    title,
    description,
    itemLabel = "Interface",
}) {
    const metrics = data?.host_metrics || {};
    const cpu = metrics.cpu || {};
    const memory = metrics.memory || {};
    const physicalPorts = data?.physical_ports || {};
    const ports = Array.isArray(physicalPorts.ports) ? physicalPorts.ports : [];
    const ping = data?.ping || {};
    const totals = physicalPorts.totals || {};

    return (
        <section className="metrics-section">
            <div className="section-heading">
                <div>
                    <h2>{title}</h2>
                    <p>{description}</p>
                </div>
                <span
                    className={`pill ${data?.status === "up" ? "pill-green" : "pill-red"}`}
                >
                    {data?.status || "-"}
                </span>
            </div>

            <div className="metrics-grid">
                <div className="card">
                    <div className="card-title-row">
                        <h3>CPU & Memory</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile
                            label="CPU Usage"
                            value={formatPercent(cpu.usage_percent)}
                        />
                        <InfoTile
                            label="Memory Usage"
                            value={formatPercent(memory.usage_percent)}
                        />
                        <InfoTile
                            label="Memory Used"
                            value={formatMegabytes(memory.used_mb)}
                        />
                        <InfoTile
                            label="Memory Total"
                            value={formatMegabytes(memory.total_mb)}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>{itemLabel} Status</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile
                            label={`Total ${itemLabel}s`}
                            value={physicalPorts.total_physical_ports ?? "-"}
                        />
                        <InfoTile
                            label={`${itemLabel}s Up`}
                            value={physicalPorts.up_physical_ports ?? "-"}
                        />
                        <InfoTile
                            label={`${itemLabel}s Down`}
                            value={physicalPorts.down_physical_ports ?? "-"}
                        />
                        <InfoTile label="Uptime" value={data?.uptime || "-"} />
                    </div>
                </div>

                <div className="card">
                    <div className="card-title-row">
                        <h3>Latency & Loss</h3>
                    </div>
                    <DiagnosticMessage text={ping.error} />
                    <div className="metrics-list">
                        <InfoTile
                            label="Avg Latency"
                            value={formatLatency(ping.avg_latency_ms)}
                        />
                        <InfoTile
                            label="Packet Loss"
                            value={formatPercent(ping.packet_loss_percent)}
                        />
                        <InfoTile
                            label="Packets Sent"
                            value={ping.sent ?? "-"}
                        />
                        <InfoTile
                            label="Packets Received"
                            value={ping.received ?? "-"}
                        />
                    </div>
                </div>

                {/* <div className="card">
                    <div className="card-title-row">
                        <h3>Errors & Discards</h3>
                    </div>
                    <div className="metrics-list">
                        <InfoTile
                            label="Input Errors"
                            value={totals.in_errors ?? "-"}
                        />
                        <InfoTile
                            label="Output Errors"
                            value={totals.out_errors ?? "-"}
                        />
                        <InfoTile
                            label="Input Discards"
                            value={totals.in_discards ?? "-"}
                        />
                        <InfoTile
                            label="Output Discards"
                            value={totals.out_discards ?? "-"}
                        />
                    </div>
                </div> */}

                {/* <div className="card metrics-grid-span-3">
                    <div className="card-title-row">
                        <h3>{itemLabel} Traffic & Status</h3>
                    </div>
                    <div className="router-port-list">
                        {ports.length ? (
                            ports.map((port) => (
                                <div
                                    className="router-port-row network-port-row"
                                    key={port.port_index}
                                >
                                    <div>
                                        <strong>{port.port_name}</strong>
                                        <span>
                                            Index {port.port_index} | Admin{" "}
                                            {port.admin_status_label || "-"} |
                                            Oper {port.oper_status_label || "-"}
                                        </span>
                                    </div>
                                    <div className="network-port-stats">
                                        <span>
                                            Speed{" "}
                                            {formatBandwidth(port.speed_mbps)}
                                        </span>
                                        <span>
                                            In {formatBytes(port.in_octets)} /
                                            Out {formatBytes(port.out_octets)}
                                        </span>
                                        <span>
                                            Err {port.in_errors ?? "-"} /{" "}
                                            {port.out_errors ?? "-"} | Discard{" "}
                                            {port.in_discards ?? "-"} /{" "}
                                            {port.out_discards ?? "-"}
                                        </span>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="empty-state">
                                No physical {itemLabel.toLowerCase()} data
                                available.
                            </div>
                        )}
                    </div>
                </div> */}
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

function DeviceNode({
    title,
    imageSrc,
    imageAlt,
    accent = "mint",
    className = "",
    onClick,
}) {
    return (
        <article className={`topology-device ${className}`.trim()}>
            <button
                type="button"
                className="topology-device-button"
                onClick={onClick}
            >
                <div className={`flow-icon-shell-${accent}`}>
                    <img
                        className="flow-icon-image"
                        src={imageSrc}
                        alt={imageAlt}
                    />
                </div>
            </button>
        </article>
    );
}

const ROUTER_PORT_SLOT_PATH = "M0 4.419V1.466L2.544 0V2.952L0 4.419Z";
const ROUTER_PORT_ROWS = {
    lower: {
        start: { x: 63.7041, y: 163.113 },
        end: { x: 107.021, y: 138.103 },
    },
    upper: {
        start: { x: 67.45, y: 160.95 },
        end: { x: 110.75, y: 135.95 },
    },
};

function getRouterPortFill(port) {
    return port.oper_status === 1
        ? "#1eb980"
        : port.oper_status === 2
          ? "#ef476f"
          : "url(#paint12_linear_1984_18161)";
}

function buildRouterPortRowData(ports, rowGeometry, minScale, maxScale) {
    if (!ports.length) return [];

    const count = ports.length;
    const spanX = rowGeometry.end.x - rowGeometry.start.x;
    const spanY = rowGeometry.end.y - rowGeometry.start.y;
    const usableRatio = count === 1 ? 0 : Math.min(0.92, 0.62 + count * 0.035);
    const paddingRatio = (1 - usableRatio) / 2;
    const stepX = count > 1 ? (spanX * usableRatio) / (count - 1) : spanX;
    const scale = Math.max(minScale, Math.min(maxScale, stepX / 4.9));

    return ports.map((port, index) => {
        const positionRatio =
            count === 1
                ? 0.5
                : paddingRatio + (usableRatio * index) / (count - 1);
        return {
            ...port,
            x: rowGeometry.start.x + spanX * positionRatio,
            y: rowGeometry.start.y + spanY * positionRatio,
            scale,
            fill: getRouterPortFill(port),
        };
    });
}

function buildRouterPortData(ports) {
    if (!ports.length) return [];

    const count = ports.length;
    if (count <= 8) {
        return buildRouterPortRowData(ports, ROUTER_PORT_ROWS.lower, 0.82, 1);
    }

    const upperCount = Math.ceil(count / 2);
    const lowerCount = count - upperCount;
    const upperPorts = ports.slice(0, upperCount);
    const lowerPorts = ports.slice(upperCount, upperCount + lowerCount);

    return [
        ...buildRouterPortRowData(
            upperPorts,
            ROUTER_PORT_ROWS.upper,
            0.58,
            0.88,
        ),
        ...buildRouterPortRowData(
            lowerPorts,
            ROUTER_PORT_ROWS.lower,
            0.58,
            0.88,
        ),
    ];
}

function buildRouterPortsMarkup(portData) {
    return portData
        .map((port) => {
            return `<path fill-rule="evenodd" clip-rule="evenodd" d="${ROUTER_PORT_SLOT_PATH}" transform="translate(${port.x.toFixed(3)} ${port.y.toFixed(3)}) scale(${port.scale.toFixed(3)})" fill="${port.fill}"/>`;
        })
        .join("");
}

function RouterDeviceNode({ title, ports = [], className = "", onClick }) {
    const portData = buildRouterPortData(ports);
    const svgMarkup = routerSvgTemplate.replace(
        "__ROUTER_PORTS__",
        buildRouterPortsMarkup(portData),
    );

    return (
        <article className={`topology-device ${className}`.trim()}>
            <button
                type="button"
                className="topology-device-button"
                onClick={onClick}
            >
                <div
                    className="flow-icon-shell-blue router-svg-shell"
                    role="img"
                    aria-label={title}
                    dangerouslySetInnerHTML={{ __html: svgMarkup }}
                />
            </button>
        </article>
    );
}

function StatusInfoBox({ title, status, metrics = [], className = "" }) {
    const online = status === "up";

    return (
        <aside className={`topology-status-box ${className}`.trim()}>
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

function TopologyMap({ nodes, links, onDeviceClick }) {
    const rsUp = links?.router_to_switch?.status === "up";
    const slUp = links?.switch_to_laptop?.status === "up";
    const srvUp = links?.router_to_server?.status === "up";
    const routerSwitchSide = getPrimarySide(links?.router_to_switch);
    const switchLaptopSide = getPrimarySide(links?.switch_to_laptop);
    const routerServerSide = getPrimarySide(links?.router_to_server);
    const routerPorts = Array.isArray(nodes?.router?.physical_ports?.ports)
        ? nodes.router.physical_ports.ports
        : [];

    return (
        <section className="traffic-flow-card">
            <div className="topology-diagram">
                <StatusInfoBox
                    className="topology-router-status"
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

                <RouterDeviceNode
                    className="topology-router-device"
                    title="Router"
                    ports={routerPorts}
                    onClick={() => onDeviceClick("router")}
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
                    className="topology-switch-device"
                    title="Switch"
                    imageSrc={switchImage}
                    imageAlt="Switch"
                    accent="mint"
                    onClick={() => onDeviceClick("switch")}
                />

                <StatusInfoBox
                    className="topology-switch-status"
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
                    className="topology-laptop-device"
                    title="Laptop"
                    imageSrc={laptopImage}
                    imageAlt="Laptop"
                    accent="cyan"
                    onClick={() => onDeviceClick("laptop")}
                />

                <StatusInfoBox
                    className="topology-laptop-status"
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

                <div className="topology-link topology-link-server-vertical">
                    <div
                        className={`flow-branch-line ${srvUp ? "flow-connector-up" : "flow-connector-down"}`}
                    ></div>
                    <div className="flow-connector-meta flow-connector-meta-vertical">
                        <span>Router to Server</span>
                        <strong>
                            {formatBandwidth(
                                getLinkSpeed(links?.router_to_server),
                            )}
                        </strong>
                    </div>
                </div>

                <DeviceNode
                    className="topology-server-device"
                    title="Server"
                    imageSrc={serverImage}
                    imageAlt="Server"
                    accent="blue"
                    onClick={() => onDeviceClick("server")}
                />

                <StatusInfoBox
                    className="topology-server-status"
                    title="Server"
                    status={nodes?.server?.status}
                    metrics={[
                        {
                            label: "Name",
                            value: nodes?.server?.name || "-",
                        },
                        { label: "Address", value: nodes?.server?.ip || "-" },
                        {
                            label: "Link",
                            value: formatBandwidth(
                                getLinkSpeed(links?.router_to_server),
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
    const [historyData, setHistoryData] = useState({ series: {} });
    const [loading, setLoading] = useState(true);
    const [sshDevice, setSshDevice] = useState(null);

    async function loadSnapshot() {
        try {
            const topologyRes = await fetch(TOPOLOGY_API_URL);
            const topologyJson = await topologyRes.json();
            setTopologyData(topologyJson);
        } catch (e) {
            setTopologyData(null);
        } finally {
            setLoading(false);
        }
    }

    async function loadHistory() {
        try {
            const response = await fetch(HISTORY_CHARTS_API_URL);
            const payload = await response.json();
            setHistoryData(payload);
        } catch {
            setHistoryData({ series: {} });
        }
    }

    useEffect(() => {
        loadSnapshot();
        loadHistory();
        const snapshotTimer = setInterval(loadSnapshot, 15000);
        const historyTimer = setInterval(loadHistory, 15000);
        return () => {
            clearInterval(snapshotTimer);
            clearInterval(historyTimer);
        };
    }, []);

    useEffect(() => {
        const socket = new WebSocket(buildStatusSocketUrl());
        socket.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                setTopologyData((current) => {
                    if (!current) return current;
                    const nextNodes = { ...current.nodes };
                    Object.entries(payload.nodes || {}).forEach(([name, statusData]) => {
                        nextNodes[name] = {
                            ...nextNodes[name],
                            status: statusData.status,
                            error: statusData.error,
                        };
                    });
                    const nextLinks = { ...current.links };
                    Object.entries(payload.links || {}).forEach(([name, statusData]) => {
                        nextLinks[name] = {
                            ...nextLinks[name],
                            status: statusData.status,
                        };
                    });
                    return {
                        ...current,
                        nodes: nextNodes,
                        links: nextLinks,
                        summary: payload.summary || current.summary,
                    };
                });
            } catch {
                return;
            }
        };
        return () => socket.close();
    }, []);

    const nodes = topologyData?.nodes || {};
    const links = topologyData?.links || {};
    const laptopNode = nodes.laptop;
    const serverNode = nodes.server;
    const sshTargets = {
        router: { id: "router", title: "Router", ip: nodes.router?.ip },
        switch: { id: "switch", title: "Switch", ip: nodes.switch?.ip },
        laptop: { id: "laptop", title: "Ubuntu Laptop", ip: laptopNode?.ip },
        server: { id: "server", title: "Server", ip: serverNode?.ip },
    };

    function openSshDevice(deviceId) {
        const target = sshTargets[deviceId];
        if (target) {
            setSshDevice(target);
        }
    }

    return (
        <div className="page">
            <h2>SNMP Topology Dashboard</h2>
            <p className="sub">
                Router, switch, and Ubuntu laptop with dynamic switch-port
                discovery
            </p>

            {loading && <div>Loading...</div>}

            <TopologyMap
                nodes={nodes}
                links={links}
                onDeviceClick={openSshDevice}
            />

            <div className="device-grid">
                <DeviceCard title="Router" data={nodes.router} />
                <DeviceCard title="Switch" data={nodes.switch} />
                <DeviceCard title="Ubuntu Laptop" data={laptopNode} />
                <DeviceCard title="Server" data={serverNode} />
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
                <LinkCard
                    title="Router to Server"
                    link={links.router_to_server}
                />
            </div>

            <NetworkDeviceMetricsPanel
                data={nodes.router}
                title="Router Metrics"
                description="CPU, memory, interface traffic, interface status, packet loss, latency, and uptime."
                itemLabel="Interface"
            />

            <NetworkDeviceMetricsPanel
                data={nodes.switch}
                title="Switch Metrics"
                description="Port status, per-port traffic, errors, discards, CPU, memory, and uptime."
                itemLabel="Port"
            />

            <HostMetricsPanel
                data={laptopNode}
                title="Laptop Metrics"
                description="Latest polled laptop telemetry from the snapshot cache"
            />

            <ServerRealtimeMetricsPanel data={serverNode} />

            <HistoricalCharts history={historyData} />

            {sshDevice ? (
                <SshTerminalModal
                    device={sshDevice}
                    onClose={() => setSshDevice(null)}
                />
            ) : null}
        </div>
    );
}
