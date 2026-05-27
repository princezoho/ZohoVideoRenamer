"""Top-level launcher for the PyInstaller-bundled desktop app.

Entry point that runs the pywebview-based single-window GUI. The previous
tkinter GUI (zoho_video_renamer.gui) is still importable for anyone using
the package as a library, but the bundled desktop app launches the
embedded webview experience for the cleanest UX (everything in one window).
"""

if __name__ == "__main__":
    from zoho_video_renamer.embedded import main
    main()
