// FRIDAY — Floating overlay window (shown during active command processing)

import SwiftUI

struct OverlayView: View {
    @ObservedObject private var state = AppState.shared
    @ObservedObject private var client = RuntimeClient.shared

    var body: some View {
        VStack(spacing: 0) {
            waveformBar
            Divider().background(Color.white.opacity(0.1))
            contentArea
        }
        .frame(width: 480)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.4), radius: 24, x: 0, y: 8)
    }

    private var waveformBar: some View {
        HStack(spacing: 12) {
            stateIndicator
            Spacer()
            Text(stateLabel)
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    private var stateIndicator: some View {
        HStack(spacing: 4) {
            ForEach(0..<5, id: \.self) { i in
                RoundedRectangle(cornerRadius: 2)
                    .fill(barColor)
                    .frame(width: 3, height: barHeight(for: i))
                    .animation(
                        .easeInOut(duration: 0.4).repeatForever().delay(Double(i) * 0.08),
                        value: state.pipelineState
                    )
            }
        }
    }

    private var contentArea: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !state.transcript.isEmpty {
                transcriptRow
            }
            if state.showCorrectionField {
                correctionRow
            }
            if !state.lastAction.isEmpty && !state.showCorrectionField {
                actionRow
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var transcriptRow: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "waveform")
                .font(.system(size: 12))
                .foregroundColor(state.isLowConfidence ? .yellow : .secondary)
                .frame(width: 16)
            Text(state.transcript)
                .font(.system(size: 14))
                .foregroundColor(state.isLowConfidence ? .yellow : .white)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var correctionRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Low confidence — what did you mean?")
                .font(.system(size: 11, design: .monospaced))
                .foregroundColor(.yellow.opacity(0.8))
            HStack(spacing: 8) {
                TextField("Correct transcript...", text: $state.correctionText)
                    .textFieldStyle(.plain)
                    .font(.system(size: 13))
                    .foregroundColor(.white)
                    .onSubmit { submitCorrection() }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.white.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 7))
                Button("Fix", action: submitCorrection)
                    .buttonStyle(.plain)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.yellow)
            }
        }
    }

    private var actionRow: some View {
        HStack(spacing: 10) {
            Image(systemName: "bolt.fill")
                .font(.system(size: 11))
                .foregroundColor(.green.opacity(0.8))
                .frame(width: 16)
            Text(state.lastAction)
                .font(.system(size: 13, design: .monospaced))
                .foregroundColor(.green)
        }
    }

    private var stateLabel: String {
        switch state.pipelineState {
        case .idle: return "idle"
        case .listeningForWake: return "listening"
        case .capturing: return "capturing..."
        case .transcribing: return "transcribing..."
        case .planning: return "planning..."
        case .executing: return "executing..."
        case .speaking: return "speaking..."
        case .confirming: return "confirm?"
        case .error: return "error"
        }
    }

    private var barColor: Color {
        switch state.pipelineState {
        case .capturing: return .yellow
        case .transcribing, .planning: return .green.opacity(0.8)
        case .executing: return .green
        case .speaking: return .blue
        case .confirming: return .orange
        case .error: return .red
        default: return Color(nsColor: .systemGray)
        }
    }

    private func barHeight(for index: Int) -> CGFloat {
        let isActive = state.pipelineState != .idle && state.pipelineState != .listeningForWake
        if isActive {
            let heights: [CGFloat] = [8, 16, 12, 20, 10]
            return heights[index % heights.count]
        }
        return 4
    }

    private func submitCorrection() {
        let c = state.correctionText.trimmingCharacters(in: .whitespaces)
        guard !c.isEmpty else { return }
        client.sendCorrection(bad: state.transcript, corrected: c)
        state.correctionText = ""
        state.showCorrectionField = false
    }
}
