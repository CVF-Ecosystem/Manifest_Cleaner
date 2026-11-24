# Sửa logic theo manifest thực tế

Status: READY
dispatchKind: INITIAL

Operator đã báo app 1.2.0 đọc sai và chỉ tới các workbook thực tế vào 24-11-2026. Đây là action sửa tương thích trong app hợp nhất. Sol 6.2 Medium phụ trách VIMC. Terra 6.1 High phụ trách VOSCO và đối chiếu VINAFCO. Astra 6.2 Medium review độc lập. Orchestrator tích hợp, kiểm build và giữ Git cục bộ.

## Phạm vi

- R2 do dùng manifest thật cục bộ. Chỉ đọc các file mẫu gốc và bản cũ, tổng hợp chứng cứ ở mức mẫu cấu trúc, vị trí và số đếm. Giữ dữ liệu nghiệp vụ ngoài Git và không có tác động đối với file cũ hay hệ thống Cảng.
- Ánh xạ tiêu chí MC51–MC54 để sửa từng hãng có bằng chứng. Tái sử dụng kiểm tra nghiệp vụ và mẫu 16 cột, giữ chốt đối chiếu dữ liệu thật thiếu hoặc xung đột. Việc sửa SOC/COC hay F/E phải xác định được chính sách và phạm vi tác động từ nguồn hoặc quy tắc cũ.
- Phạm vi ghi project này là manifest_cleaner/, tests/, tài liệu liên quan, CVF continuity và bản EXE app riêng. Build lưu riêng, giữ artifact 1.2.0 cũ. Git cục bộ. Thời gian 120 phút là trần kỹ thuật của action.
- Phân tách kết luận trước/sau đối chiếu phần dữ liệu đã có. Hãng chưa có cặp đầu ra không được gọi đã khớp bản cũ.

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
    "path": "docs/roadmaps/MC_LEGACY_COMPAT.md",
    "heading": "## Tiêu chí nghiệm thu",
    "sha256": "aaad337852f08a260cf209957e4a72af1f41d0e90ca94ebc7462e131bb12e66a"
  },
  "milestone": {
    "id": "MC2",
    "consumer": "Người xử lý manifest tại Cảng",
    "outcome": "App hợp nhất xử lý đúng manifest thật theo căn cứ nguồn và đầu ra tham chiếu",
    "checkpoint": {
      "trigger": "Đã có đối chiếu trên các cặp dữ liệu cục bộ",
      "owner": "Orchestrator và reviewer độc lập",
      "decision": "Chấp nhận theo phạm vi đúng dữ liệu đã kiểm hoặc giữ phần còn thiếu"
    }
  },
  "phase": "DISPATCH",
  "action": {
    "kind": "IMPLEMENT",
    "selected": [
      "MC51",
      "MC52",
      "MC53",
      "MC54"
    ],
    "owner": "Orchestrator và worker được phân công",
    "output": "Bản vá app và bằng chứng đối chiếu hai cặp có thật, kiểm nguồn VINAFCO, EXE local",
    "budgetMinutes": 120,
    "stop": "Giữ riêng khác biệt nghiệp vụ chưa có căn cứ, không tiếp tục sửa suy đoán hoặc ghi vào file gốc. Sau một lượt sửa thất bại audit trước lượt phụ thuộc.",
    "next": "Reviewer độc lập và kiểm đúng bản đóng gói."
  },
  "rows": [
    {
      "id": "MC51",
      "state": "NOT_STARTED",
      "gap": "Bản 1.2.0 chưa đạt đối chiếu đầu vào nghiệp vụ cho phần này.",
      "owner": "Orchestrator / maintainer",
      "destination": "Mốc MC51 trong roadmap MC2",
      "evidence": []
    },
    {
      "id": "MC52",
      "state": "NOT_STARTED",
      "gap": "Bản 1.2.0 chưa đạt đối chiếu đầu vào nghiệp vụ cho phần này.",
      "owner": "Orchestrator / maintainer",
      "destination": "Mốc MC52 trong roadmap MC2",
      "evidence": []
    },
    {
      "id": "MC53",
      "state": "NOT_STARTED",
      "gap": "Bản 1.2.0 chưa đạt đối chiếu đầu vào nghiệp vụ cho phần này.",
      "owner": "Orchestrator / maintainer",
      "destination": "Mốc MC53 trong roadmap MC2",
      "evidence": []
    },
    {
      "id": "MC54",
      "state": "NOT_STARTED",
      "gap": "Bản 1.2.0 chưa đạt đối chiếu đầu vào nghiệp vụ cho phần này.",
      "owner": "Orchestrator / maintainer",
      "destination": "Mốc MC54 trong roadmap MC2",
      "evidence": []
    }
  ],
  "supportingWork": [],
  "conclusions": {
    "tranche": "PENDING",
    "trancheSummary": "Cần sửa và kiểm",
    "trancheEvidence": [],
    "product": "PENDING",
    "productSummary": "Nghiệm thu nghiệp vụ còn mở",
    "acceptance": [],
    "owner": "Orchestrator"
  }
}
```
