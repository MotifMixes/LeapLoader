# Streams one image out of the zip and writes only its non-zero 512-byte sectors:
# records of (u32 sector index, 512 bytes). Usage: sparse_extract.ps1 ZIP ENTRY OUT
param([string]$Zip, [string]$Entry, [string]$Out)
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
Add-Type -ReferencedAssemblies System.IO.Compression, System.Linq, System.Runtime, System.Collections -TypeDefinition @"
using System; using System.IO; using System.IO.Compression; using System.Linq;
public static class SparseExtract {
    public static string Run(string zip, string entry, string outPath) {
        using (var fs = File.OpenRead(zip))
        using (var z = new ZipArchive(fs, ZipArchiveMode.Read))
        using (var src = z.Entries.First(e => e.Name == entry).Open())
        using (var dst = new FileStream(outPath, FileMode.Create, FileAccess.Write, FileShare.Read)) {
            var buf = new byte[512];
            long sector = 0, kept = 0;
            while (true) {
                int n = 0;
                while (n < 512) { int r = src.Read(buf, n, 512 - n); if (r <= 0) break; n += r; }
                if (n == 0) break;
                bool nz = false;
                for (int k = 0; k < n; k++) if (buf[k] != 0) { nz = true; break; }
                if (nz) { dst.Write(BitConverter.GetBytes((uint)sector), 0, 4); dst.Write(buf, 0, 512); kept++; }
                sector++;
                if (n < 512) break;
            }
            return "sectors " + sector + ", kept " + kept;
        }
    }
}
"@
[SparseExtract]::Run($Zip, $Entry, $Out)
