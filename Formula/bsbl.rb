class Bsbl < Formula
  include Language::Python::Virtualenv

  desc "Newspaper-styled terminal UI for MLB scores and players"
  homepage "https://github.com/tylersuits1/bsbl"
  url "https://github.com/tylersuits1/bsbl.git",
      tag:      "v0.3.0",
      revision: "1ef2fb98f404c3b3f5aff4ad434d9e449796d64d"
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    system libexec/"bin/python3.12", "-m", "pip", "install", "--no-cache-dir", buildpath
    bin.install_symlink libexec/"bin/bsbl"
  end

  test do
    system libexec/"bin/python3.12", "-c", "import bsbl"
  end
end
