import React from "react";

interface SocketServerStatusProps {
  /** When true, dot is blue (connected); when false, red (disconnected). Default: false. */
  active?: boolean;
}

const SocketServerStatus = ({ active = false }: SocketServerStatusProps) => {
  return (
    <div className="flex items-center gap-2 font-mono text-xs text-gray-300">
      <span
        className={`h-2 w-2 rounded-full animate-pulse ${
          active ? "bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]" : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"
        }`}
        aria-hidden
      />
      <span>{active ? "Connected" : "Disconnected"}</span>
    </div>
  );
};

export default SocketServerStatus;
