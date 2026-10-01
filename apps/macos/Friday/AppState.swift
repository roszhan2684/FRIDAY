// FRIDAY — Shared observable app state
// All SwiftUI views observe this single source of truth.

import Foundation
import Combine

enum PipelineState: String, Codable {
    case idle
    case listeningForWake = "listening_for_wake"
    case capturing
    case transcribing
    case planning
    case confirming
    case executing
    case speaking
    case error
}

struct HistoryItem: Identifiable, Codable {
    let id: String
    let transcript: String
    let toolCalled: String?
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case id, transcript, timestamp
        case toolCalled = "tool_called"
    }
}

struct PendingConfirmation {
    let tool: String
    let args: [String: Any]
    let spoken: String
}

final class AppState: ObservableObject {
    static let shared = AppState()

    @Published var pipelineState: PipelineState = .idle
    @Published var transcript: String = ""
    @Published var transcriptConfidence: Double = 1.0
    @Published var isLowConfidence: Bool = false
    @Published var lastAction: String = ""
    @Published var lastResult: String = ""
    @Published var isConnected: Bool = false
    @Published var pendingConfirmation: PendingConfirmation? = nil
    @Published var commandHistory: [HistoryItem] = []
    @Published var correctionText: String = ""
    @Published var showCorrectionField: Bool = false
    @Published var errorMessage: String? = nil

    var menuBarIcon: String {
        switch pipelineState {
        case .idle, .listeningForWake: return "waveform"
        case .capturing: return "waveform.badge.mic"
        case .transcribing, .planning: return "ellipsis.circle"
        case .executing: return "bolt.fill"
        case .speaking: return "speaker.wave.2.fill"
        case .confirming: return "questionmark.circle.fill"
        case .error: return "exclamationmark.triangle.fill"
        }
    }

    var menuBarTint: String {
        switch pipelineState {
        case .idle, .listeningForWake: return "systemGray"
        case .capturing: return "systemYellow"
        case .transcribing, .planning, .executing: return "systemGreen"
        case .speaking: return "systemBlue"
        case .confirming: return "systemOrange"
        case .error: return "systemRed"
        }
    }
}
