# PR0163 pre-demo checklist

Date: 2026-09-18

## Must pass before demo

- [ ] Aramina 0.2.12 Nova_257 left: preflight PASS
- [ ] Aramina 0.2.12 Nova_257 left: fresh/recoverable execution PASS
- [ ] Aramina 0.2.13 Nova_257 left: preflight PASS
- [ ] Aramina 0.2.13 Nova_257 left: fresh/recoverable execution PASS
- [ ] Aramina 0.2.12 Nova_384 left: classified unsupported input
- [ ] Aramina 0.2.13 Nova_384 left: classified unsupported input
- [ ] Bremen Nova_376: completed/report available
- [ ] Aramina completed trace reports completed
- [ ] Aramina failed trace points at real failing stage
- [ ] H5 catalog preserves patient_display_name when identity exists
- [ ] Frontend shows patient_display_name before display_name
- [ ] StandardResult has no `aramina` wrapper
- [ ] StandardResult has no `bremen` wrapper
- [ ] `report.payload.risk_score` unchanged
- [ ] `report.payload.technical_demo_only` unchanged
- [ ] Exact Bremen replay recovers existing report
- [ ] Exact Aramina replay recovers existing report
- [ ] Aramina left/right are distinct analyses
- [ ] Same source with different model_id is a distinct analysis
- [ ] Bremen model_name verified from package-owned metadata

## Already verified in production

- [x] Bremen current execution works
- [x] Aramina 0.2.12 fresh happy execution works
- [x] Aramina 0.2.13 fresh happy execution works
- [x] Aramina 0.2.12 safe unsupported-input failure works
- [x] Aramina 0.2.13 safe unsupported-input failure works
- [x] Bremen report endpoint works
- [x] Aramina report endpoint works
- [x] StandardResult is a bare object for Bremen
- [x] StandardResult is a bare object for Aramina
- [x] Exact duplicate replay returns an existing job handle
- [x] Existing result can be recovered after replay

## Known issues to fix

- [ ] Aramina preflight false-negatives
- [ ] Aramina trace projection
- [ ] Failed trace projection
- [ ] Patient identity/catalog/frontend label
- [ ] Bremen model_name metadata verification
