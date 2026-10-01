// FRIDAY — macOS App Entry Point
// Menu bar only app (no Dock icon). Global hotkey: Cmd+Shift+F.

import SwiftUI
import AppKit

@main
struct FridayApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            SettingsView()
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var popover: NSPopover?
    var permissionsWindow: NSWindow?

    private var client: RuntimeClient { RuntimeClient.shared }
    private var state: AppState { AppState.shared }
    private var stateObserver: Any?
    private let hasShownPermissionsKey = "friday.hasShownPermissions"

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        setupMenuBar()
        setupPopover()
        setupHotkey()
        client.connect()

        stateObserver = NotificationCenter.default.addObserver(
            forName: .fridayStateChanged, object: nil, queue: .main
        ) { [weak self] _ in self?.updateMenuBarIcon() }

        if !UserDefaults.standard.bool(forKey: hasShownPermissionsKey) {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                self.showPermissions()
            }
        }
    }

    // MARK: — Menu Bar

    private func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        guard let button = statusItem?.button else { return }
        button.image = NSImage(systemSymbolName: "waveform", accessibilityDescription: "FRIDAY")
        button.image?.isTemplate = true
        button.action = #selector(togglePopover)
        button.target = self
    }

    private func updateMenuBarIcon() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            let name = self.state.menuBarIcon
            self.statusItem?.button?.image = NSImage(systemSymbolName: name, accessibilityDescription: "FRIDAY")
            self.statusItem?.button?.image?.isTemplate = true
        }
    }

    // MARK: — Popover

    private func setupPopover() {
        let p = NSPopover()
        p.contentSize = NSSize(width: 360, height: 260)
        p.behavior = .transient
        p.contentViewController = NSHostingController(rootView: MenuBarView())
        popover = p
    }

    @objc private func togglePopover() {
        guard let button = statusItem?.button else { return }
        if let p = popover {
            p.isShown ? p.performClose(nil) : p.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }

    // MARK: — Global Hotkey: Cmd+Shift+F

    private func setupHotkey() {
        NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard event.modifierFlags.contains([.command, .shift]),
                  event.keyCode == 3  // 'f'
            else { return }
            self?.activateFriday()
        }
    }

    private func activateFriday() {
        guard let button = statusItem?.button else { return }
        DispatchQueue.main.async {
            guard let p = self.popover, !p.isShown else { return }
            p.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }

    // MARK: — Permissions Onboarding

    func showPermissions() {
        var done = false
        let hosting = NSHostingController(
            rootView: PermissionsView(didComplete: Binding(
                get: { done },
                set: { val in
                    done = val
                    if val {
                        UserDefaults.standard.set(true, forKey: self.hasShownPermissionsKey)
                        self.permissionsWindow?.close()
                    }
                }
            ))
        )
        let win = NSWindow(contentViewController: hosting)
        win.title = "FRIDAY — Permissions Setup"
        win.setContentSize(NSSize(width: 440, height: 420))
        win.styleMask = [.titled, .closable]
        win.center()
        permissionsWindow = win
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

extension Notification.Name {
    static let fridayStateChanged = Notification.Name("FridayStateChanged")
}
