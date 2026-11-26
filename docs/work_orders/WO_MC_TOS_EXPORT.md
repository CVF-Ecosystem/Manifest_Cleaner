# Xuất theo mẫu TOS và cửa sổ Đổi B/L

Status: READY
dispatchKind: INITIAL

Ngày 26-11-2026, operator chốt bốn điểm, ghi trong [roadmap MC3](../roadmaps/MC_TOS_EXPORT.md):

- Dùng một mẫu xuất chung theo form TOS `Manifest/Vtos.xlsx`.
- Đổi B/L làm ở một chỗ tách riêng do người dùng tự thực hiện.
- Ghi chú để trống trong file Excel.
- Trọng lượng lấy theo manifest gốc.

Operator yêu cầu làm và sẽ tự import thử trên TOS. Ngày 26-11-2026, reviewer độc lập (Claude subagent, Opus 5.5) duyệt work order với kết luận ADMIT_WITH_NOTES. Các ghi chú đã được đưa vào roadmap và work order này.

Trong lúc làm, một agent giữ hai vai ORCHESTRATOR và IMPLEMENTATION_WORKER, và tự kiểm có ghi lại. Commit vật liệu chỉ được làm khi đủ hai điều kiện: có review độc lập cho phần triển khai (gate reviewer_fast), và operator yêu cầu commit. Bước kiểm của người là operator import thử trên TOS (MC64).

## Phạm vi

- Rủi ro R2, vì file đi thẳng vào hệ thống TOS của Cảng. Chỉ đọc cục bộ file mẫu TOS, manifest và bill trong `Manifest/`. Không ghi vào các file đó và không đưa dữ liệu nghiệp vụ vào Git. Không có tác động trực tiếp tới TOS.
- Thực hiện MC61 đến MC63:
  - Thay hai mẫu 16 cột bằng mẫu TOS 46 cột cho cả ba hãng. Giữ quy tắc giá trị theo hãng.
  - Thêm module đổi B/L và cửa sổ GUI mở từ thanh công cụ.
  - Cập nhật test, fixture golden và tài liệu liên quan.
- Phạm vi ghi:
  - `manifest_cleaner/`, `tests/`, `scripts/create_samples.py`, `samples/`.
  - Tài liệu: README, `docs/` (roadmap, work order, review, catalog, DEVELOPER_HANDOFF, ADAPTER_CONTRACT, AUDIT_FIXES).
  - Trong `AGENTS.md` của project, chỉ sửa dòng quy tắc 16 cột trong mục "Quy tắc của app hợp nhất".
  - CVF continuity và `PACKAGE_MANIFEST.sha256`.
- Không phát hành EXE trong lượt này.
- Tách khỏi MC52:
  - Base của lượt này là `510526b`.
  - Working tree đã có thay đổi VOSCO DOOR-CY/CY-DOOR chưa commit, thuộc MC52, gồm `manifest_cleaner/carriers/vosco/adapter.py`, `tests/test_vosco_v110.py`, `docs/reviews/LEGACY_COMPAT_REVIEW.md` và các dòng MC52 trong handoff và `IMPLEMENTATION_STATUS.json`. MC3 không sửa hai file mã và test này.
  - Đối chiếu 297 dòng ở MC63 dựa trên bản sửa MC52.
  - Khi operator yêu cầu commit, MC52 được commit trước trong một commit riêng. `PACKAGE_MANIFEST.sha256` được tạo lại cho mỗi commit.
- Trần kỹ thuật: 180 phút.

## Gate-To-Role Closeability Contract

closeabilityContractVersion: cvf.gate-role-closeability@1.0.0
closeabilityDisposition: CLOSEABLE
returnTimeRecheck: REQUIRED_BEFORE_REPAIR
implementationTopologyPolicy: BOUNDED_PATH_FAMILIES
foreseeableFileSplitDisposition: COVERED_BY_BOUNDED_PATH_FAMILY

| gateId | mustPassBy | repairOwner | repairPhase | mutationSurface | topology | commitOwner | commitPhase | dependsOn |
|---|---|---|---|---|---|---|---|---|
| authorization_review | PRE_DISPATCH | orchestrator | PRE_DISPATCH | Work order and local activation review | EXACT_PATHS | orchestrator | DISPATCH_COMMIT | NONE |
| pre_dispatch_gate | PRE_DISPATCH | orchestrator | PRE_DISPATCH | Work order and activation receipt | EXACT_PATHS | orchestrator | DISPATCH_COMMIT | authorization_review |
| dispatch_continuity | IMPLEMENTATION | session-sync-steward | IMPLEMENTATION | AGENT_HANDOFF_V1_2026-11-24.md material-SHA marker | EXACT_PATHS | session-sync-steward | DISPATCH_CONTINUITY_COMMIT | pre_dispatch_gate |
| focused_checker_tests | IMPLEMENTATION | implementation-worker | IMPLEMENTATION | tests/ and manifest_cleaner/ | BOUNDED_PATH_FAMILIES | commit-steward | MATERIAL_COMMIT | dispatch_continuity |
| adif_integrity | IMPLEMENTATION | orchestrator | IMPLEMENTATION | Allowed work-order paths and Git baseline | BOUNDED_PATH_FAMILIES | commit-steward | MATERIAL_COMMIT | dispatch_continuity |
| pre_implementation_autorun | IMPLEMENTATION | orchestrator | IMPLEMENTATION | Local CVF runner receipts and handoff | BOUNDED_PATH_FAMILIES | commit-steward | MATERIAL_COMMIT | focused_checker_tests, adif_integrity |
| worker_return_fast | WORKER_RETURN | implementation-worker | WORKER_RETURN | Changed paths and focused test output | BOUNDED_PATH_FAMILIES | commit-steward | MATERIAL_COMMIT | pre_implementation_autorun |
| reviewer_fast | REVIEW | reviewer | REVIEW | Independent review and verification | BOUNDED_PATH_FAMILIES | commit-steward | MATERIAL_COMMIT | worker_return_fast |
| pre_commit | PRE_MATERIAL_COMMIT | commit-steward | PRE_MATERIAL_COMMIT | Exact staged diff and gate receipt | EXACT_PATHS | commit-steward | MATERIAL_COMMIT | reviewer_fast |
| terminal_completion_review | POST_MATERIAL | reviewer | POST_MATERIAL | Review of observed local results | BOUNDED_PATH_FAMILIES | commit-steward | MATERIAL_COMMIT | pre_commit |
| continuity | CONTINUITY_COMMIT | session-sync-steward | CONTINUITY_COMMIT | Active state, memory, handoff and implementation status | EXACT_PATHS | session-sync-steward | CONTINUITY_COMMIT | terminal_completion_review |
| committed_range_closure | POST_MATERIAL_CLOSURE | commit-steward | POST_MATERIAL_CLOSURE | Local Git material and continuity range | EXACT_PATHS | session-sync-steward | CONTINUITY_COMMIT | continuity |


## Milestone coverage

```cvf-milestone-coverage-json
{
  "schemaVersion": "cvf.milestoneCoverage@1.0.0",
  "authority": {
    "path": "docs/roadmaps/MC_TOS_EXPORT.md",
    "heading": "## Tiêu chí nghiệm thu",
    "sha256": "afb98ff7925ae385eba8bfab15400bcf3aa3fbd374f6ccbbe9d96e2c6ab63348"
  },
  "milestone": {
    "id": "MC3",
    "consumer": "Người xử lý manifest tại Cảng",
    "outcome": "File xuất import thẳng vào TOS, gồm cả trường hợp đổi B/L giữa hai hãng",
    "checkpoint": {
      "trigger": "Đã có file mẫu TOS từ app và kết quả đối chiếu cục bộ",
      "owner": "Operator tại Cảng",
      "decision": "Chấp nhận sau khi import thử trên TOS hoặc trả về danh sách cột cần sửa"
    }
  },
  "phase": "DISPATCH",
  "action": {
    "kind": "IMPLEMENT",
    "selected": [
      "MC61",
      "MC62",
      "MC63"
    ],
    "owner": "Orchestrator và implementation worker",
    "output": "Mẫu xuất TOS 46 cột, cửa sổ Đổi B/L, hồi quy và đối chiếu cục bộ với Vtos.xlsx",
    "budgetMinutes": 180,
    "stop": "Không suy đoán mã TOS chưa có bằng chứng. Không ghi vào file nguồn. Sau một lượt sửa thất bại, audit trước lượt phụ thuộc.",
    "next": "Operator import thử trên TOS (MC64) và reviewer độc lập."
  },
  "rows": [
    {"id": "MC61", "state": "NOT_STARTED", "gap": "Mỗi hãng một mẫu 16 cột riêng", "owner": "Orchestrator / maintainer", "destination": "Mốc MC61 trong roadmap MC3", "evidence": []},
    {"id": "MC62", "state": "NOT_STARTED", "gap": "Đổi B/L đang làm tay trên TOS", "owner": "Orchestrator / maintainer", "destination": "Mốc MC62 trong roadmap MC3", "evidence": []},
    {"id": "MC63", "state": "NOT_STARTED", "gap": "Chưa có hồi quy cho mẫu TOS", "owner": "Orchestrator / maintainer", "destination": "Mốc MC63 trong roadmap MC3", "evidence": []},
    {"id": "MC64", "state": "NOT_STARTED", "gap": "Chưa import thử trên TOS", "owner": "Operator", "destination": "Mốc MC64 trong roadmap MC3", "evidence": []}
  ],
  "supportingWork": [],
  "conclusions": {
    "tranche": "PENDING",
    "trancheSummary": "Cần làm và kiểm",
    "trancheEvidence": [],
    "product": "PENDING",
    "productSummary": "Chờ import thử trên TOS",
    "acceptance": [],
    "owner": "Orchestrator"
  }
}
```
