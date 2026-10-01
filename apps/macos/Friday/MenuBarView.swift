// FRIDAY — Menu bar popover view
// Shows current state, last transcript/action, quick command input.

import SwiftUI

struct MenuBarView: View {
    @ObservedObject private var state = AppState.shared
    @ObservedObject private var client = RuntimeClient.shared
    @State private var typedCommand: String = ""
    @FocusState private var commandFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            headerBar
            if !state.isConnected {
                Divider().background(Color.white.opacity(0.08))
                offlineBanner
            }
            Divider().background(Color.white.opacity(0.08))
            statusRow
            Divider().background(Color.white.opacity(0.08))
            commandInput
            if state.showCorrectionField {
                Divider().background(Color.white.opacity(0.08))
                correctionRow
            }
            if let conf = state.pendingConfirmation {
                Divider().background(Color.white.opacity(0.08))
                confirmationRow(conf)
            }
        }
        .frame(width: 360)
        .background(Color(nsColor: .windowBackgroundColor).opacity(0.0))
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var headerBar: some View {
        HStack {
            Image(systemName: state.menuBarIcon)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(stateColor)
            Text("FRIDAY")
                .font(.system(size: 13, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
            Spacer()
            Circle()
                .fill(state.isConnected ? Color.green : Color.red)
                .frame(width: 7, height: 7)
            Text(state.isConnected ? "online" : "offline")
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(.secondary)
            Button(action: openSettings) {
                Image(systemName: "gearshape")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    private func openSettings() {
        NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
    }

    private var statusRow: some View {
        VStack(alignment: .leading, spacing: 4) {
            if !state.transcript.isEmpty {
                Label {
                    Text(state.transcript)
                        .font(.system(size: 12))
                        .foregroundColor(state.isLowConfidence ? .yellow : .white.opacity(0.85))
                        .lineLimit(2)
                } icon: {
                    Image(systemName: "waveform")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
            }
            if !state.lastAction.isEmpty {
                Label {
                    Text(state.lastAction)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundColor(.green.opacity(0.9))
                } icon: {
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 10))
                        .foregroundColor(.green.opacity(0.7))
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .frame(minHeight: 36)
    }

    @ViewBuilder
    private var offlineBanner: some View {
        if !state.isConnected {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 11))
                    .foregroundColor(.orange)
                Text("Runtime offline")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.orange)
                Spacer()
                Button("Start") { startRuntime() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.orange)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(Color.orange.opacity(0.06))
        }
    }

    private func startRuntime() {
        let script = Bundle.main.bundlePath
            .components(separatedBy: "/apps/macos").first ?? ""
        let startScript = "\(script)/scripts/start.sh"
        let task = Process()
        task.launchPath = "/usr/bin/env"
        task.arguments = ["bash", startScript]
        try? task.run()
    }

    private var commandInput: some View {
        HStack(spacing: 8) {
            TextField("Type a command, Boss...", text: $typedCommand)
                .textFieldStyle(.plain)
                .font(.system(size: 12, design: .monospaced))
                .foregroundColor(.white)
                .focused($commandFocused)
                .onSubmit { submitCommand() }
            Button(action: submitCommand) {
                Image(systemName: "return")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(typedCommand.isEmpty ? .secondary : .white)
            }
            .buttonStyle(.plain)
            .disabled(typedCommand.isEmpty)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    private var correctionRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Low confidence — correct me:")
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(.yellow.opacity(0.8))
            HStack {
                TextField("What did you actually say?", text: $state.correctionText)
                    .textFieldStyle(.plain)
                    .font(.system(size: 12))
                    .foregroundColor(.white)
                    .onSubmit { submitCorrection() }
                Button("Fix", action: submitCorrection)
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.yellow)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Color.yellow.opacity(0.05))
    }

    private func confirmationRow(_ conf: PendingConfirmation) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Confirm: \(conf.tool)")
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundColor(.orange)
            HStack(spacing: 12) {
                Button("Yes, do it") {
                    client.sendConfirmation(confirmed: true)
                    state.pendingConfirmation = nil
                }
                .buttonStyle(.plain)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.green)

                Button("Cancel") {
                    client.sendConfirmation(confirmed: false)
                    state.pendingConfirmation = nil
                }
                .buttonStyle(.plain)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.red)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Color.orange.opacity(0.05))
    }

    private var stateColor: Color {
        switch state.pipelineState {
        case .idle, .listeningForWake: return Color(nsColor: .systemGray)
        case .capturing: return .yellow
        case .transcribing, .planning, .executing: return .green
        case .speaking: return .blue
        case .confirming: return .orange
        case .error: return .red
        }
    }

    private func submitCommand() {
        let cmd = typedCommand.trimmingCharacters(in: .whitespaces)
        guard !cmd.isEmpty else { return }
        client.sendCommand(cmd)
        typedCommand = ""
    }

    private func submitCorrection() {
        let corrected = state.correctionText.trimmingCharacters(in: .whitespaces)
        guard !corrected.isEmpty else { return }
        client.sendCorrection(bad: state.transcript, corrected: corrected)
        state.correctionText = ""
        state.showCorrectionField = false
    }
}
