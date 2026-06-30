import type { WSMessage } from './types';

type Handler = (msg: WSMessage) => void;

export class WebSocketClient {
	private ws: WebSocket | null = null;
	private url: string;
	private handlers: Set<Handler> = new Set();
	private reconnectTimer: number | null = null;
	private heartbeatTimer: number | null = null;
	private shouldReconnect = true;

	constructor(url?: string) {
		const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
		this.url = url ?? `${proto}//${location.host}/ws`;
	}

	connect() {
		if (this.ws?.readyState === WebSocket.OPEN) return;
		this.shouldReconnect = true;
		try {
			this.ws = new WebSocket(this.url);
		} catch {
			this.scheduleReconnect();
			return;
		}

		this.ws.onopen = () => {
			this.startHeartbeat();
		};

		this.ws.onmessage = (e) => {
			try {
				const msg = JSON.parse(e.data) as WSMessage;
				this.handlers.forEach((h) => h(msg));
			} catch {
				// ignore malformed
			}
		};

		this.ws.onclose = () => {
			this.stopHeartbeat();
			if (this.shouldReconnect) this.scheduleReconnect();
		};

		this.ws.onerror = () => {
			this.ws?.close();
		};
	}

	private scheduleReconnect() {
		if (this.reconnectTimer) return;
		this.reconnectTimer = window.setTimeout(() => {
			this.reconnectTimer = null;
			this.connect();
		}, 3000);
	}

	private startHeartbeat() {
		this.heartbeatTimer = window.setInterval(() => {
			if (this.ws?.readyState === WebSocket.OPEN) {
				this.ws.send('ping');
			}
		}, 30000);
	}

	private stopHeartbeat() {
		if (this.heartbeatTimer) {
			clearInterval(this.heartbeatTimer);
			this.heartbeatTimer = null;
		}
	}

	onMessage(handler: Handler): () => void {
		this.handlers.add(handler);
		return () => this.handlers.delete(handler);
	}

	disconnect() {
		this.shouldReconnect = false;
		this.stopHeartbeat();
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
		this.ws?.close();
		this.ws = null;
	}
}
