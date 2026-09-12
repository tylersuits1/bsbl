class Bsbl < Formula
  include Language::Python::Virtualenv

  desc "Newspaper-styled terminal UI for MLB scores and players"
  homepage "https://github.com/tylersuits1/bsbl"
  url "https://github.com/tylersuits1/bsbl.git",
      tag:      "v0.4.0",
      revision: "6a8e14e6595fe072649b68a4f88f11f8e04fd83d"
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
