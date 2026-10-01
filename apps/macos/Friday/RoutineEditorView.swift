// FRIDAY — Routine editor: view, create, and manage routines

import SwiftUI

struct RoutineItem: Identifiable, Codable {
    let id: String
    let name: String
    let use_count: Int
    let updated_at: String
}

struct RoutinesResponse: Codable {
    let routines: [RoutineItem]
}

struct RoutineEditorView: View {
    @State private var routines: [RoutineItem] = []
    @State private var isLoading = true
    @State private var errorMessage: String? = nil
    @ObservedObject private var client = RuntimeClient.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            Divider()
            if isLoading {
                ProgressView("Loading routines...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let err = errorMessage {
                Text(err).foregroundColor(.red).padding()
            } else {
                routineList
            }
        }
        .frame(width: 480, height: 380)
        .task { await loadRoutines() }
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Routines")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                Text("Tap a routine to run it. Swipe to delete.")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            Spacer()
            Button("Refresh") { Task { await loadRoutines() } }
                .buttonStyle(.plain)
                .font(.system(size: 11))
                .foregroundColor(.blue)
        }
        .padding()
    }

    private var routineList: some View {
        List(routines) { routine in
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(routine.name)
                        .font(.system(size: 14, weight: .semibold))
                    Text("Used \(routine.use_count) times")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
                Spacer()
                Button("Run") {
                    client.sendCommand("run \(routine.name.lowercased())")
                }
                .buttonStyle(.plain)
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(.green)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(Color.green.opacity(0.12))
                .clipShape(Capsule())
            }
            .padding(.vertical, 4)
        }
        .listStyle(.plain)
    }

    private func loadRoutines() async {
        isLoading = true
        errorMessage = nil
        guard let url = URL(string: "http://127.0.0.1:7700/routines/") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoded = try JSONDecoder().decode(RoutinesResponse.self, from: data)
            routines = decoded.routines
        } catch {
            errorMessage = "Could not load routines: \(error.localizedDescription)"
        }
        isLoading = false
    }
}
