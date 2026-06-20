import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import fs from "fs/promises";
import path from "path";

const execFileAsync = promisify(execFile);

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // Create temp directory inside workspace
    const tempDir = path.join(process.cwd(), "temp");
    await fs.mkdir(tempDir, { recursive: true });

    // Generate unique file names
    const timestamp = Date.now();
    const fileExt = path.extname(file.name);
    const originalNameWithoutExt = path.basename(file.name, fileExt);
    const safeBaseName = originalNameWithoutExt.replace(/[^a-zA-Z0-9_-]/g, "_");
    
    const inputFileName = `${timestamp}_${safeBaseName}${fileExt}`;
    const outputFileName = `redacted_${timestamp}_${safeBaseName}${fileExt}`;

    const inputPath = path.join(tempDir, inputFileName);
    const outputPath = path.join(tempDir, outputFileName);

    // Write input file to temp path
    await fs.writeFile(inputPath, buffer);

    try {
      // Execute the Python script
      const pythonScriptPath = path.join(process.cwd(), "python", "redact.py");
      
      // Use python3 to invoke the script
      await execFileAsync("python3", [pythonScriptPath, inputPath, outputPath]);

      // Read output file content
      const redactedBuffer = await fs.readFile(outputPath);

      // Clean up input and output files
      await fs.unlink(inputPath).catch(() => {});
      await fs.unlink(outputPath).catch(() => {});

      // Determine content type based on extension
      let contentType = "application/octet-stream";
      if (fileExt.toLowerCase() === ".docx") {
        contentType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      } else if (fileExt.toLowerCase() === ".pptx") {
        contentType = "application/vnd.openxmlformats-officedocument.presentationml.presentation";
      } else if (fileExt.toLowerCase() === ".pdf") {
        contentType = "application/pdf";
      } else if (fileExt.toLowerCase() === ".png") {
        contentType = "image/png";
      } else if (fileExt.toLowerCase() === ".jpg" || fileExt.toLowerCase() === ".jpeg") {
        contentType = "image/jpeg";
      }

      // Return the file for download
      const response = new NextResponse(redactedBuffer, {
        status: 200,
        headers: {
          "Content-Type": contentType,
          "Content-Disposition": `attachment; filename="redacted_${file.name}"`,
        },
      });

      return response;
    } catch (cmdError: any) {
      // Clean up on command failure
      await fs.unlink(inputPath).catch(() => {});
      await fs.unlink(outputPath).catch(() => {});
      
      console.error("Redaction command failed:", cmdError);
      return NextResponse.json(
        { 
          error: "Redaction failed", 
          details: cmdError.stderr || cmdError.message || String(cmdError) 
        }, 
        { status: 500 }
      );
    }
  } catch (error: any) {
    console.error("API Route error:", error);
    return NextResponse.json({ error: "Server error", details: error.message }, { status: 500 });
  }
}
