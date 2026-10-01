// FRIDAY — WebSocket client connecting Swift app to Python runtime

import Foundation
import Combine

final class RuntimeClient: NSObject, ObservableObject, URLSessionWebSocketDelegate {
    static let shared = RuntimeClient()

    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession!
    private var state: AppState { AppState.shared }

    private let runtimeBaseURL = "http://127.0.0.1:7700"
    private let runtimeWSURL = "ws://127.0.0.1:7700/ws"

    private var reconnectTask: Task<Void, Never>?

    override init() {
        super.init()
        session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
    }

    func connect() {
        guard let url = URL(string: runtimeWSURL) else { return }
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        receiveLoop()
    }

    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
    }

    // MARK: - Sending

    func sendCommand(_ text: String) {
        send(["type": "command", "text": text])
    }

    func sendCorrection(bad: String, corrected: String, audioHash: String = "") {
        send(["type": "correction", "bad": bad, "corrected": corrected, "audio_hash": audioHash])
    }

    func sendConfirmation(confirmed: Bool) {
        send(["type": "confirm", "confirmed": confirmed])
    }

    private func send(_ dict: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: dict),
              let string = String(data: data, encoding: .utf8) else { return }
        webSocket?.send(.string(string)) { error in
            if let error = error {
                print("[RuntimeClient] Send error: \(error)")
            }
        }
    }

    // MARK: - Receiving

    private func receiveLoop() {
        webSocket?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                if case .string(let text) = message {
                    self.handleEvent(text)
                }
                self.receiveLoop()
            case .failure(let error):
                print("[RuntimeClient] Receive error: \(error)")
                Task { @MainActor in
                    self.state.isConnected = false
                }
                self.scheduleReconnect()
            }
        }
    }

    private func handleEvent(_ json: String) {
        guard let data = json.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        let type = obj["type"] as? String ?? ""
        let payload = obj["payload"] as? [String: Any] ?? [:]

        Task { @MainActor in
            switch type {
            case "state_change":
                if let s = payload["state"] as? String, let ps = PipelineState(rawValue: s) {
                    self.state.pipelineState = ps
                    if ps == .idle || ps == .listeningForWake {
                        self.state.showCorrectionField = false
                    }
                }
            case "transcript":
                self.state.transcript = payload["text"] as? String ?? ""
                self.state.transcriptConfidence = payload["confidence"] as? Double ?? 1.0
                let lowConf = payload["low_confidence"] as? Bool ?? false
                self.state.isLowConfidence = lowConf
                self.state.showCorrectionField = lowConf
            case "action":
                self.state.lastAction = payload["tool"] as? String ?? ""
            case "result":
                self.state.lastResult = payload["output"] as? String ?? ""
                let success = payload["success"] as? Bool ?? false
                if !success, let err = payload["error"] as? String {
                    self.state.errorMessage = err
                }
            case "confirm_required":
                self.state.pendingConfirmation = PendingConfirmation(
                    tool: payload["tool"] as? String ?? "",
                    args: payload["args"] as? [String: Any] ?? [:],
                    spoken: payload["spoken"] as? String ?? ""
                )
            case "error":
                self.state.errorMessage = payload["message"] as? String
            default:
                break
            }
        }
    }

    // MARK: - Reconnect

    private func scheduleReconnect() {
        reconnectTask?.cancel()
        reconnectTask = Task {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            guard !Task.isCancelled else { return }
            self.connect()
        }
    }

    // MARK: - URLSessionWebSocketDelegate

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            self.state.isConnected = true
            print("[RuntimeClient] Connected to FRIDAY runtime")
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            self.state.isConnected = false
        }
        scheduleReconnect()
    }

    // MARK: - HTTP helpers

    func checkHealth() async -> Bool {
        guard let url = URL(string: "\(runtimeBaseURL)/health") else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}
