cask "mage-voyance-beta" do
  version "0.1.0"
  sha256 "PLACEHOLDER"

  url "https://github.com/imaginary-cherry/mageflow/releases/download/app%2Fv#{version}-beta/Mageflow.Viewer_#{version}_aarch64.dmg"
  name "Mage Voyance (Beta)"
  desc "Desktop viewer for MageFlow task orchestration workflows (beta channel)"
  homepage "https://github.com/imaginary-cherry/mageflow"

  depends_on arch: :arm64

  app "Mageflow Viewer.app"

  zap trash: [
    "~/Library/Application Support/dev.mageflow.viewer",
    "~/Library/Caches/dev.mageflow.viewer",
    "~/Library/Preferences/dev.mageflow.viewer.plist",
  ]
end
