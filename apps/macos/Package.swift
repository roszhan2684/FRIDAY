// swift-tools-version: 5.9
import PackageDescription

// FRIDAY macOS App — Swift Package
// Open this folder in Xcode: File → Open → select apps/macos/
// Or build from CLI:  swift build -c release
// Run from CLI:       swift run

let package = Package(
    name: "Friday",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "Friday",
            path: "Friday",
            exclude: [
                "Info.plist",
                "Friday.entitlements",
                "Assets.xcassets"
            ]
        )
    ]
)
