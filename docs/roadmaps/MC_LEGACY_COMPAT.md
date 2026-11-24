# Sửa tương thích manifest nghiệp vụ

Ngày 24-11-2026. Người dùng phát hiện bản 1.2.0 báo sai trên manifest VIMC và chỉ ra các cặp nguồn/đầu ra cũ. Dùng cặp có danh tính chuyến khớp và kiểm tra ngược lại với vùng nguồn trước khi sửa. Bản đã xử lý là căn cứ so sánh, có thể chứa giá trị cần đối chiếu.

## Tiêu chí nghiệm thu

| ID | Kết quả cần đạt |
|---|---|
| MC51 | VIMC BS2622S-TT giữ đủ 157 quan hệ container–B/L, đọc đủ chủ hàng theo đúng khối vai trò và bảo toàn số seal, kích cỡ, trạng thái, trọng lượng và tên hàng đã khớp. Giải thích chênh mã operator và chỉ thay khi có căn cứ. Mã container sai từ nguồn vẫn cần xử lý có căn cứ. |
| MC52 | So VOSCO FF2601S với bản xuất cũ, loại bản ghi từ tiêu đề được chứng minh và sửa ghép trọng lượng theo nguồn. Giữ ứng viên thực bị hỏng, và phân biệt phần khác do quy tắc F/E, trọng lượng hoặc đối chiếu. |
| MC53 | Kiểm kê mẫu VINAFCO, dùng cặp có thể xác minh. Nếu thiếu đầu ra cùng chuyến, ghi rõ và kiểm nguồn hiện có cùng bộ golden. Giữ các hồi quy chọn sheet và đối soát. |
| MC54 | Sửa trong project hợp nhất, không đổi các tệp người dùng. Hồi quy tự chứa hoặc kiểm chứng cục bộ không đưa dữ liệu nghiệp vụ vào Git. Chạy bộ kiểm thử đúng pin, reviewer độc lập và build EXE mới tách khỏi EXE 1.2.0 đang chạy. |

## Bằng chứng ban đầu

- VIMC 157 dòng và 157 cặp khóa khớp. 315 lỗi gồm 157 mục thiếu consignee từ adapter, 157 lỗi thiếu giá trị chủ hàng từ engine và một mã dạng bốn chữ bốn số cùng xuất hiện trên file cũ. Sheet1 ghi header trên dòng 16, nhãn header chỉ cột B nhưng cả 52 bộ dấu 1), 2), 3) nằm trong cột A. Trọng lượng, kích cỡ, seal, F/E và tên hàng đã khớp. 21 mã SVM cũ thành VMC cần truy nguồn.
- VOSCO đọc 346 dòng, 309 cặp khóa khớp đầu ra cũ. Các ứng viên thừa có hình thức hai từ nối dấu gạch hoặc dấu gạch chéo; cần xác minh nhóm tiêu đề và ảnh hưởng lên trọng lượng. Bản 1.2.0 khớp 279/309 trọng lượng theo ngưỡng nửa đơn vị làm tròn.
- VINAFCO ba workbook đã thấy dưới folder cũ cần xác minh vai trò theo cột/sheet. Mức hoàn tất tại Cảng nằm ngoài lần sửa cục bộ.

## Coverage snapshot

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
  "phase": "PLAN",
  "action": {
    "kind": "PLAN",
    "selected": [],
    "owner": "Orchestrator",
    "output": "Tiêu chí khớp dữ liệu và kế hoạch đối chiếu cục bộ",
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
