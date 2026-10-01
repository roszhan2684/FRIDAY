// FRIDAY — Permissions onboarding shown on first launch

import SwiftUI
import AppKit

struct Permission: Identifiable {
    let id = UUID()
    let icon: String
    let title: String
    let detail: String
    let settingsPath: String
    var granted: Bool = false
}

struct PermissionsView: View {
    @State private var permissions: [Permission] = [
        Permission(
            icon: "mic.fill",
            title: "Microphone",
            detail: "Required for wake word detection and voice commands.",
            settingsPath: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
        ),
        Permission(
            icon: "accessibility",
            title: "Accessibility",
            detail: "Required for global hotkey (Cmd+Shift+F) and app switching.",
            settingsPath: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ),
        Permission(
            icon: "folder.fill",
            title: "Full Disk Access",
            detail: "Required for file search across all folders.",
            settingsPath: "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
        ),
    ]
    @Binding var didComplete: Bool

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            permissionsList
            Divider()
            footer
        }
        .frame(width: 440)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var header: some View {
        VStack(spacing: 8) {
            Image(systemName: "waveform.circle.fill")
                .font(.system(size: 48))
                .foregroundColor(.blue)
            Text("Friday needs a few permissions")
                .font(.system(size: 18, weight: .bold))
            Text("Grant access below so Friday can hear you,\ncontrol apps, and find your files.")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.vertical, 24)
    }

    private var permissionsList: some View {
        VStack(spacing: 0) {
            ForEach(Array(permissions.enumerated()), id: \.element.id) { idx, perm in
                HStack(spacing: 14) {
                    Image(systemName: perm.icon)
                        .font(.system(size: 22))
                        .foregroundColor(.blue)
                        .frame(width: 32)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(perm.title)
                            .font(.system(size: 14, weight: .semibold))
                        Text(perm.detail)
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    Button("Open") {
                        if let url = URL(string: perm.settingsPath) {
                            NSWorkspace.shared.open(url)
                        }
                    }
                    .buttonStyle(.plain)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 5)
                    .background(Color.blue)
                    .clipShape(Capsule())
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 12)

                if idx < permissions.count - 1 {
                    Divider().padding(.leading, 70)
                }
            }
        }
    }

    private var footer: some View {
        HStack {
            Text("You can revisit this later in Friday's menu.")
                .font(.system(size: 11))
                .foregroundColor(.secondary)
            Spacer()
            Button("Done") { didComplete = true }
                .buttonStyle(.plain)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.white)
                .padding(.horizontal, 20)
                .padding(.vertical, 7)
                .background(Color.blue)
                .clipShape(Capsule())
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 14)
    }
}
