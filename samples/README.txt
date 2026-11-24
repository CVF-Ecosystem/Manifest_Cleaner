TAT CA FILE TRONG THU MUC NAY LA DU LIEU GIA LAP, KHONG CO KHACH HANG THUC.

1. Mo ung dung, chon hang VOSCO/VIMC/VINAFCO.
2. Chon dung DEMO_<HANG>_INPUT.xlsx; moi lan chi xu ly mot manifest.
3. Xem bang ket qua; xuat voi ten moi va so sanh DEMO_<HANG>_EXPECTED.xlsx.
4. VIMC demo co ca dang trong luong truoc (tan) va sau (kg), khong chon ten tau.
5. DEMO_VIMC_NEEDS_REVIEW.xlsx co chu y thieu chu hang va mot dong mo ho.
   Ung dung phai giu cac dong, hien loi va yeu cau kiem tra truoc khi xuat.
6. File REVIEW.json v2 mo lai duoc bang Mo phien da luu; giu file INPUT.xlsx cung thu muc.
   File JSON luu bang chung nguon va lich su; khong dung de import vao Cang.
7. EXPECTED.xlsx o thu muc samples duoc tao bang chinh chuong trinh, chi de thu thao tac.
   Golden kiem chung doc lap nam o tests/fixtures/golden_v110 (ky vong viet tay).
   Ca hai bo deu la du lieu tong hop, chua duoc he thong Cang xac nhan.

Tao lai bo demo: python scripts/create_samples.py --output samples
