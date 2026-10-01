// FRIDAY — Memory viewer: shows what FRIDAY has learned

import SwiftUI

struct MemoryView: View {
    @State private var aliases: [(phrase: String, path: String)] = []
    @State private var history: [(transcript: String, tool: String, timestamp: String)] = []
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $selectedTab) {
                Text("Aliases").tag(0)
                Text("History").tag(1)
            }
            .pickerStyle(.segmented)
            .padding()

            if selectedTab == 0 {
                aliasesTab
            } else {
                historyTab
            }
        }
        .frame(width: 500, height: 400)
        .task { await loadData() }
    }

    private var aliasesTab: some View {
        List(aliases, id: \.phrase) { item in
            HStack {
                Text(item.phrase)
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(.primary)
                Spacer()
                Text(item.path)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
    }

    private var historyTab: some View {
        List(history, id: \.transcript) { item in
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.transcript)
                        .font(.system(.body))
                    Text(item.tool)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundColor(.secondary)
                }
                Spacer()
                Text(item.timestamp)
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
            }
        }
    }

    private func loadData() async {
        guard let url = URL(string: "http://127.0.0.1:7700/memory/aliases") else { return }
        // Data is loaded from the runtime HTTP API (to be implemented in router.py)
        // For now this is a placeholder — data will populate when API is wired up
    }
}
