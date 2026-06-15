"use client";

import { useState, useRef, DragEvent, ChangeEvent } from "react";

interface RedactionFile {
  id: string;
  name: string;
  size: number;
  ext: string;
  status: "pending" | "processing" | "success" | "error";
  url: string | null;
  error?: string;
}

export default function Home() {
  const [files, setFiles] = useState<RedactionFile[]>([]);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles: File[]) => {
    const supportedExts = [".docx", ".pdf", ".pptx"];
    
    newFiles.forEach((file) => {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!supportedExts.includes(ext)) return;
      
      const fileId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const newFileObj: RedactionFile = {
        id: fileId,
        name: file.name,
        size: file.size,
        ext: ext,
        status: "pending",
        url: null,
      };
      
      setFiles((prev) => [...prev, newFileObj]);
      processFile(fileId, file);
    });
  };

  const processFile = async (id: string, file: File) => {
    setFiles((prev) =>
      prev.map((f) => (f.id === id ? { ...f, status: "processing" } : f))
    );

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/redact", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || errData.details || "Redaction failed");
      }

      // Read output file as blob
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, status: "success", url } : f
        )
      );

      // Trigger automatic download
      const a = document.createElement("a");
      a.href = url;
      a.download = `redacted_${file.name}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err: any) {
      console.error(err);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id
            ? { ...f, status: "error", error: err.message || "Something went wrong" }
            : f
        )
      );
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const removeFileFromList = (id: string) => {
    setFiles((prev) => {
      const fileToRemove = prev.find(f => f.id === id);
      if (fileToRemove?.url) {
        window.URL.revokeObjectURL(fileToRemove.url);
      }
      return prev.filter(f => f.id !== id);
    });
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="title-badge">Phase 1 POC</div>
        <h1 className="dashboard-title">Redaction & Drafting Engine</h1>
        <p className="dashboard-subtitle">
          Clean documents of sensitive markers, credentials, registration numbers, 
          and school branding while guaranteeing original style preservation.
        </p>
      </header>

      <main className="dashboard-grid">
        {/* Left Side: Upload & Queue */}
        <section className="panel" id="upload-panel">
          <div
            className={`dropzone ${dragActive ? "drag-active" : ""}`}
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={triggerFileInput}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: "none" }}
              multiple
              accept=".docx,.pdf,.pptx"
            />
            <div className="upload-icon-wrapper">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="upload-instruction">
              Drag & Drop your document here or <span style={{ color: "var(--color-primary)" }}>Browse</span>
            </div>
            <div className="upload-formats">Supported formats: DOCX, PDF, PPTX</div>
          </div>
        </section>

        {/* Right Side: Active Processing & Features */}
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          {/* Active File List */}
          <section className="panel" style={{ flexGrow: 1 }}>
            <h2 className="panel-title">
              <span className="indicator"></span>
              Document Queue ({files.length})
            </h2>

            {files.length === 0 ? (
              <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)", fontSize: "0.9rem" }}>
                No active uploads. Add documents to begin redaction.
              </div>
            ) : (
              <div className="file-list">
                {files.map((file) => (
                  <div className="file-item" key={file.id}>
                    <div className="file-info">
                      <div
                        className={`file-icon-box ${
                          file.ext === ".docx"
                            ? "file-icon-docx"
                            : file.ext === ".pdf"
                            ? "file-icon-pdf"
                            : "file-icon-pptx"
                            ? "file-icon-pptx"
                            : ""
                        }`}
                      >
                        {file.ext.substring(1).toUpperCase()}
                      </div>
                      <div className="file-details">
                        <div className="file-name" title={file.name}>
                          {file.name}
                        </div>
                        <div className="file-meta">
                          {formatSize(file.size)}
                          <span style={{ color: "rgba(255,255,255,0.15)" }}>|</span>
                          {file.status === "pending" && (
                            <span className="badge badge-pending">Queued</span>
                          )}
                          {file.status === "processing" && (
                            <span className="badge badge-processing">
                              <span className="spinner" style={{ marginRight: "4px", width: "10px", height: "10px", borderWidth: "1px" }}></span>
                              Redacting
                            </span>
                          )}
                          {file.status === "success" && (
                            <span className="badge badge-success">Cleaned</span>
                          )}
                          {file.status === "error" && (
                            <span className="badge badge-error" title={file.error}>
                              Failed
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      {file.status === "success" && file.url && (
                        <a
                          href={file.url}
                          download={`redacted_${file.name}`}
                          className="btn btn-icon-only"
                          title="Download cleaned document"
                        >
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                          </svg>
                        </a>
                      )}
                      <button
                        onClick={() => removeFileFromList(file.id)}
                        className="btn btn-secondary btn-icon-only"
                        title="Remove file"
                      >
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Engine Features Card */}
          <section className="panel features-panel">
            <h2 className="panel-title">
              <span className="indicator" style={{ backgroundColor: "var(--color-accent)" }}></span>
              Redaction Rules
            </h2>
            
            <div className="feature-item">
              <div className="feature-icon-box">✓</div>
              <div className="feature-info">
                <div className="feature-title">Student IDs & Credentials</div>
                <div className="feature-desc">Matches pattern codes (ST12345, APP99881, etc.)</div>
              </div>
            </div>

            <div className="feature-item">
              <div className="feature-icon-box">✓</div>
              <div className="feature-info">
                <div className="feature-title">Personal Contact Info</div>
                <div className="feature-desc">Removes emails, phone numbers, and zip codes</div>
              </div>
            </div>

            <div className="feature-item">
              <div className="feature-icon-box">✓</div>
              <div className="feature-info">
                <div className="feature-title">University Branding</div>
                <div className="feature-desc">Removes known university domains and matches logo shapes via perceptual hashing</div>
              </div>
            </div>
          </section>
        </div>
      </main>

      <footer className="footer">
        Document Redaction Engine POC • Phase 1
      </footer>
    </div>
  );
}
