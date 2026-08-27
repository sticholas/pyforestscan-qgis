# Finalization Architecture

Finalization consumes the immutable `frozen_execution_plan.json`, durable work-unit statuses, and final artifacts. It must never call the scientific planner after execution begins.

Terminal order is: merge products, apply the exact polygon mask, validate outputs, write metadata, register outputs, notify QGIS, then publish terminal state. A registration or presentation error cannot turn validated scientific work into a scientific failure.

Recovery requires every required area to be `Complete` or `CompleteNoData`, permits planned `SkippedOutsidePolygon` areas, and validates each final raster before rebuilding `generated_outputs.json`. Recovery writes `SCIENCE_COMPLETE_FINALIZATION_REPAIRED` and never invokes an adapter or worker.
