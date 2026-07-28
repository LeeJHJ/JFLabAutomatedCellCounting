import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.config.AutoThresholdParmameters
import qupath.ext.braian.config.WatershedCellDetectionConfig
import static qupath.lib.scripting.QP.*

var ch = new ImageChannelTools("DAPI-T4", getCurrentImageData())   // imageData ctor (avoids the v1.1.0 NPE)

// current setting is prominence=500, nPeak=2. Sweep prominence DOWN to preview lower thresholds:
[500, 300, 200, 100, 50].each { prom ->
    var t = new AutoThresholdParmameters()
    t.setResolutionLevel(0)        // MUST match BraiAn.yml (default 4 = your "no peak" error)
    t.setSmoothWindowSize(15)
    t.setnPeak(2)                  // keep 2 (skip the background peak)
    t.setPeakProminence(prom as double)
    try   { println "prominence=${prom}  ->  DAPI threshold = " + WatershedCellDetectionConfig.findThreshold(ch, t) }
    catch (e) { println "prominence=${prom}  ->  no valid peak" }
}
// reference: how low it can go (1st peak above background):
var lo = new AutoThresholdParmameters(); lo.setResolutionLevel(0); lo.setSmoothWindowSize(15); lo.setnPeak(1); lo.setPeakProminence(100d)
try { println "nPeak=1 (background floor) -> " + WatershedCellDetectionConfig.findThreshold(ch, lo) } catch (e) { println "nPeak=1 -> no valid peak" }