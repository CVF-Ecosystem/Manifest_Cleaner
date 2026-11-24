# Triển khai roadmap Manifest Cleaner

Status: READY
dispatchKind: INITIAL

Operator giao thi công roadmap và đã chốt bản phát triển ngang cấp với Core ngày 24-11-2026. Orchestrator giữ quyền tích hợp, Git cục bộ và phân công. Worker chính Terra 6.1 High. Các phần phức tạp có thể giao Sol 6.2 Medium. Reviewer độc lập Astra 6.2 Medium theo chỉ định. Worker tiếp nhận từng lát việc có đường dẫn sở hữu riêng. Bắt đầu M11 rồi M12, sau đó xử lý M21/M22 và M31. M41 giữ hành vi 3 hãng, M32 kiểm bản đã tích hợp. M42 chờ yêu cầu nghiệp vụ.

## Phạm vi và tiêu chí

- R1 cho sửa và kiểm trên fixture tổng hợp trong project. Manifest nguồn có sẵn được dùng cục bộ, chỉ đọc, kết quả bằng chứng chỉ ghi số lượng và vị trí, không sao chép dữ liệu nghiệp vụ sang repo. Kết luận nhập Cảng giữ tại mốc nghiệp vụ.
- M11/M12 bảo toàn dòng chi tiết thiếu mã, nhận bảng tổng hợp VINAFCO theo cấu trúc, ghi tọa độ và đối chiếu số lượng theo mã kích cỡ, container duy nhất và B/L trong đúng phạm vi. M21 cho chọn sheet ngay sau khi phát hiện mơ hồ. M22 thêm rà soát hữu hạn các dòng VOSCO lệch cột trong vùng.
- M31 kiểm mã hóa stdout/stderr qua subprocess. M41 tập trung thông tin hãng và cấu hình đóng gói, giữ mẫu Excel, cách làm tròn và nhóm số lượng hiện tại. M32 dùng dependency pin và EXE Windows cho luồng mở, kiểm tra, lưu, mở lại và xuất ở thư mục tạm.
- Phạm vi ghi: package manifest_cleaner/, tests/, cấu hình build ManifestCleaner.spec, hồ sơ ROADMAP/CVF, tài liệu sản phẩm liên quan và bản build cục bộ. Git chỉ lưu lịch sử project này. Dùng thư viện và công cụ build từ môi trường project, không đẩy repo hoặc phát hành ra ngoài.
- Luồng code đã có engine/exporter và test fixtures; giữ tương thích schema v2, golden 3 hãng, kiểm ghi cặp Excel/JSON và nguồn. Ngân sách 120 phút là trần điều phối kỹ thuật cho action này, không phải cấp quyền chi phí hoặc phát hành.

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
    "path": "docs/roadmaps/MANIFEST_CLEANER.md",
    "heading": "## Mốc và tiêu chí nghiệm thu",
    "sha256": "dcd00c7073a34231c8d5e65c45a0b0b2aaff980f18c5c57eb0cd3f138928e463"
  },
  "milestone": {
    "id": "MC1",
    "consumer": "Người vận hành manifest tại Cảng",
    "outcome": "Đọc và đối soát đúng dữ liệu rồi xuất đúng mẫu; dễ tích hợp hãng mới.",
    "checkpoint": {
      "trigger": "Có bằng chứng từng mốc",
      "owner": "Orchestrator và reviewer độc lập",
      "decision": "Xác nhận phần đạt và ghi phần còn giữ"
    }
  },
  "phase": "DISPATCH",
  "action": {
    "kind": "IMPLEMENT",
    "selected": [
      "M11",
      "M12",
      "M21",
      "M22",
      "M31",
      "M32",
      "M41"
    ],
    "owner": "Orchestrator và implementation workers được giao",
    "output": "Bản sửa app, hồi quy và kiểm chứng Windows trong phạm vi roadmap",
    "budgetMinutes": 120,
    "stop": "Dừng nhánh phụ thuộc nếu chưa được admit, gặp quy tắc nghiệp vụ ngoài phạm vi hoặc đủ bằng chứng. Audit trước lượt sửa phụ thuộc sau khi thất bại.",
    "next": "Review độc lập theo mốc; giữ M42 ở trạng thái chờ dữ liệu nghiệp vụ"
  },
  "rows": [
    {
      "id": "M01",
      "state": "IMPLEMENTED_UNPROVED",
      "gap": "Cần hồ sơ đánh giá được review và gate xác nhận.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M01 checkpoint",
      "evidence": []
    },
    {
      "id": "M11",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M11 checkpoint",
      "evidence": []
    },
    {
      "id": "M12",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M12 checkpoint",
      "evidence": []
    },
    {
      "id": "M21",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M21 checkpoint",
      "evidence": []
    },
    {
      "id": "M22",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M22 checkpoint",
      "evidence": []
    },
    {
      "id": "M31",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M31 checkpoint",
      "evidence": []
    },
    {
      "id": "M32",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M32 checkpoint",
      "evidence": []
    },
    {
      "id": "M41",
      "state": "NOT_STARTED",
      "gap": "Cần triển khai và kiểm chứng đúng tiêu chí của roadmap.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M41 checkpoint",
      "evidence": []
    },
    {
      "id": "M42",
      "state": "NOT_STARTED",
      "gap": "Cần hãng và quy tắc/mẫu đầu ra do nghiệp vụ xác định.",
      "owner": "Orchestrator / maintainer",
      "destination": "Roadmap criterion M42 checkpoint",
      "evidence": []
    }
  ],
  "supportingWork": [],
  "conclusions": {
    "tranche": "PENDING",
    "trancheSummary": "Chờ đánh giá và thi công",
    "trancheEvidence": [],
    "product": "PENDING",
    "productSummary": "Chưa có bằng chứng nghiệm thu Windows và nhập Cảng",
    "acceptance": [],
    "owner": "Orchestrator"
  }
}
```
