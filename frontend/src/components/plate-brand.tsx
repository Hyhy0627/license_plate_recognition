import Link from "next/link";
import { ScanLine } from "lucide-react";

export default function PlateBrand() {
  return (
    <Link href="/" className="plate-brand" aria-label="PlateSight — Trang chủ">
      <span className="plate-brand-mark" aria-hidden="true"><ScanLine size={23} /></span>
      <span className="plate-brand-copy">
        <strong>PlateSight</strong>
        <small>NHẬN DIỆN BIỂN SỐ</small>
      </span>
    </Link>
  );
}
