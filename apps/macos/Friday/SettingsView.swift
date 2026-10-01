// FRIDAY — Settings window: tabs for memory, routines, and permissions

import SwiftUI

struct SettingsView: View {
    @State private var selectedTab = "memory"

    var body: some View {
        TabView(selection: $selectedTab) {
            MemoryView()
                .tabItem { Label("Memory", systemImage: "brain") }
                .tag("memory")

            RoutineEditorView()
                .tabItem { Label("Routines", systemImage: "list.bullet.rectangle") }
                .tag("routines")

            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
                .tag("about")
        }
        .frame(minWidth: 500, minHeight: 420)
    }
}

struct AboutView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "waveform.circle.fill")
                .font(.system(size: 56))
                .foregroundColor(.blue)
            Text("FRIDAY")
                .font(.system(size: 22, weight: .bold, design: .monospaced))
            Text("v0.1.0")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
            Divider().frame(maxWidth: 200)
            VStack(alignment: .leading, spacing: 8) {
                aboutRow("Wake word", "hey friday (hey_mycroft placeholder)")
                aboutRow("STT", "mlx-whisper (Metal)")
                aboutRow("LLM", "llama3.2 via Ollama")
                aboutRow("TTS", "Murf.ai (Matthew voice)")
                aboutRow("Runtime", "localhost:7700")
            }
            .padding(.horizontal, 40)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private func aboutRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundColor(.secondary)
                .frame(width: 100, alignment: .trailing)
            Text(value)
                .font(.system(size: 12))
        }
    }
}
