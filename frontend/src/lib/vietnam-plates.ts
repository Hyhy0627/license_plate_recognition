/**
 * Cơ sở tri thức giải mã Biển số xe cơ giới Việt Nam
 * Căn cứ Thông tư 24/2023/TT-BCA và quy chuẩn Cục Cảnh sát giao thông
 */

export interface PlateMetadata {
  rawPlate: string;
  normalizedPlate: string;
  line1: string;
  line2: string;
  isTwoLine: boolean;
  provinceCode: string;
  provinceName: string;
  regionName: string;
  series: string;
  vehicleCategory: string;
  vehicleDescription: string;
  colorType: "white" | "blue" | "yellow" | "red";
  colorName: string;
  colorDescription: string;
  isValidFormat: boolean;
}

// Danh mục 63 tỉnh, thành phố và cơ quan trung ương
const PROVINCE_MAP: Record<string, { name: string; region: string }> = {
  "11": { name: "Cao Bằng", region: "Đông Bắc Bộ" },
  "12": { name: "Lạng Sơn", region: "Đông Bắc Bộ" },
  "14": { name: "Quảng Ninh", region: "Đông Bắc Bộ" },
  "15": { name: "Hải Phòng", region: "Đồng bằng sông Hồng" },
  "16": { name: "Hải Phòng", region: "Đồng bằng sông Hồng" },
  "17": { name: "Thái Bình", region: "Đồng bằng sông Hồng" },
  "18": { name: "Nam Định", region: "Đồng bằng sông Hồng" },
  "19": { name: "Phú Thọ", region: "Đông Bắc Bộ" },
  "20": { name: "Thái Nguyên", region: "Đông Bắc Bộ" },
  "21": { name: "Yên Bái", region: "Tây Bắc Bộ" },
  "22": { name: "Tuyên Quang", region: "Đông Bắc Bộ" },
  "23": { name: "Hà Giang", region: "Đông Bắc Bộ" },
  "24": { name: "Lào Cai", region: "Tây Bắc Bộ" },
  "25": { name: "Lai Châu", region: "Tây Bắc Bộ" },
  "26": { name: "Sơn La", region: "Tây Bắc Bộ" },
  "27": { name: "Điện Biên", region: "Tây Bắc Bộ" },
  "28": { name: "Hòa Bình", region: "Tây Bắc Bộ" },
  "29": { name: "Hà Nội", region: "Thủ đô Hà Nội" },
  "30": { name: "Hà Nội", region: "Thủ đô Hà Nội" },
  "31": { name: "Hà Nội", region: "Thủ đô Hà Nội" },
  "32": { name: "Hà Nội", region: "Thủ đô Hà Nội" },
  "33": { name: "Hà Nội", region: "Thủ đô Hà Nội" },
  "40": { name: "Hà Nội", region: "Thủ đô Hà Nội" },
  "34": { name: "Hải Dương", region: "Đồng bằng sông Hồng" },
  "35": { name: "Ninh Bình", region: "Đồng bằng sông Hồng" },
  "36": { name: "Thanh Hóa", region: "Bắc Trung Bộ" },
  "37": { name: "Nghệ An", region: "Bắc Trung Bộ" },
  "38": { name: "Hà Tĩnh", region: "Bắc Trung Bộ" },
  "43": { name: "Đà Nẵng", region: "Duyên hải Nam Trung Bộ" },
  "47": { name: "Đắk Lắk", region: "Tây Nguyên" },
  "48": { name: "Đắk Nông", region: "Tây Nguyên" },
  "49": { name: "Lâm Đồng", region: "Tây Nguyên" },
  "41": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "50": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "51": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "52": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "53": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "54": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "55": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "56": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "57": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "58": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "59": { name: "TP. Hồ Chí Minh", region: "Đông Nam Bộ" },
  "60": { name: "Đồng Nai", region: "Đông Nam Bộ" },
  "61": { name: "Đồng Nai", region: "Đông Nam Bộ" },
  "62": { name: "Long An", region: "Đồng bằng sông Cửu Long" },
  "63": { name: "Tiền Giang", region: "Đồng bằng sông Cửu Long" },
  "64": { name: "Vĩnh Long", region: "Đồng bằng sông Cửu Long" },
  "65": { name: "Cần Thơ", region: "Đồng bằng sông Cửu Long" },
  "66": { name: "Đồng Tháp", region: "Đồng bằng sông Cửu Long" },
  "67": { name: "An Giang", region: "Đồng bằng sông Cửu Long" },
  "68": { name: "Kiên Giang", region: "Đồng bằng sông Cửu Long" },
  "69": { name: "Cà Mau", region: "Đồng bằng sông Cửu Long" },
  "70": { name: "Tây Ninh", region: "Đông Nam Bộ" },
  "71": { name: "Bến Tre", region: "Đồng bằng sông Cửu Long" },
  "72": { name: "Bà Rịa - Vũng Tàu", region: "Đông Nam Bộ" },
  "73": { name: "Quảng Bình", region: "Bắc Trung Bộ" },
  "74": { name: "Quảng Trị", region: "Bắc Trung Bộ" },
  "75": { name: "Thừa Thiên Huế", region: "Bắc Trung Bộ" },
  "76": { name: "Quảng Ngãi", region: "Duyên hải Nam Trung Bộ" },
  "77": { name: "Bình Định", region: "Duyên hải Nam Trung Bộ" },
  "78": { name: "Phú Yên", region: "Duyên hải Nam Trung Bộ" },
  "79": { name: "Khánh Hòa", region: "Duyên hải Nam Trung Bộ" },
  "80": { name: "Cục CSGT - Cơ quan Trung ương", region: "Trung ương / Bộ ngành" },
  "81": { name: "Gia Lai", region: "Tây Nguyên" },
  "82": { name: "Kon Tum", region: "Tây Nguyên" },
  "83": { name: "Sóc Trăng", region: "Đồng bằng sông Cửu Long" },
  "84": { name: "Trà Vinh", region: "Đồng bằng sông Cửu Long" },
  "85": { name: "Ninh Thuận", region: "Duyên hải Nam Trung Bộ" },
  "86": { name: "Bình Thuận", region: "Duyên hải Nam Trung Bộ" },
  "88": { name: "Vĩnh Phúc", region: "Đồng bằng sông Hồng" },
  "89": { name: "Hưng Yên", region: "Đồng bằng sông Hồng" },
  "90": { name: "Hà Nam", region: "Đồng bằng sông Hồng" },
  "92": { name: "Quảng Nam", region: "Duyên hải Nam Trung Bộ" },
  "93": { name: "Bình Phước", region: "Đông Nam Bộ" },
  "94": { name: "Bạc Liêu", region: "Đồng bằng sông Cửu Long" },
  "95": { name: "Hậu Giang", region: "Đồng bằng sông Cửu Long" },
  "97": { name: "Bắc Kạn", region: "Đông Bắc Bộ" },
  "98": { name: "Bắc Giang", region: "Đông Bắc Bộ" },
  "99": { name: "Bắc Ninh", region: "Đồng bằng sông Hồng" },
};

export function parseVietnamPlate(raw: string, explicitPlateType?: string | null): PlateMetadata {
  const clean = (raw || "").trim().toUpperCase().replace(/[^A-Z0-9-.\s]/g, "");

  // Kiểm tra 2 dòng: có dấu xuống dòng, hoặc có khoảng trắng chia 2 phần (VD: "27-B1 258.88"), hoặc explicitPlateType === "two_line"
  let isTwoLine = explicitPlateType === "two_line";
  let line1 = "";
  let line2 = "";

  // Phân tách nếu chuỗi có dạng "27-B1 258.88" hoặc "27B1 25888" hoặc "59-G2 777.77"
  const spaceParts = clean.split(/[\s\n]+/);
  if (spaceParts.length >= 2) {
    line1 = spaceParts[0];
    line2 = spaceParts.slice(1).join(" ");
    // Nếu phần đầu có 1 chữ + 1 số (như B1, G2, K1, F3...) -> thường là biển xe máy 2 dòng
    if (/^[0-9]{2}[-A-Z]{1,2}[0-9A-Z]?$/.test(line1)) {
      isTwoLine = true;
    }
  } else if (clean.includes("-") && clean.length >= 8) {
    const dashIdx = clean.indexOf("-");
    const sub = clean.slice(dashIdx + 1);
    // Nếu dạng 30A-111.11 -> biển 1 dòng
    if (/^[A-Z][0-9.\s]+$/.test(sub)) {
      isTwoLine = explicitPlateType === "two_line";
      line1 = clean;
    } else {
      line1 = clean;
    }
  } else {
    line1 = clean;
  }

  if (isTwoLine && !line2 && clean.length >= 7) {
    // Thử tách tự động: 4 ký tự đầu (vd: 27-B1 hoặc 27B1) và phần còn lại
    const match = clean.match(/^([0-9]{2}[-–]?[A-Z0-9]{1,2})\s*([0-9.\s]{4,6})$/);
    if (match) {
      line1 = match[1];
      line2 = match[2].trim();
    }
  }

  // Lấy mã tỉnh (2 chữ số đầu)
  const provMatch = clean.match(/^([0-9]{2})/);
  const provCode = provMatch ? provMatch[1] : "";
  const province = PROVINCE_MAP[provCode] || {
    name: provCode ? `Tỉnh/Thành mã ${provCode}` : "Chưa xác định",
    region: "Toàn quốc",
  };

  // Xác định sê-ri xe
  const seriesMatch = clean.match(/^[0-9]{2}[-–]?([A-Z0-9]{1,2})/);
  const series = seriesMatch ? seriesMatch[1] : "";

  // Phân loại phương tiện
  let vehicleCategory = "Phương tiện cơ giới đường bộ";
  let vehicleDescription = "Xe cá nhân hoặc doanh nghiệp lưu thông đường bộ.";

  // Nếu biển 2 dòng hoặc sê-ri có 2 ký tự (chữ + số ví dụ B1, G2...) -> Xe máy
  if (isTwoLine || /^[A-Z][0-9]$/.test(series)) {
    vehicleCategory = "Xe mô tô / xe máy hai bánh";
    vehicleDescription = `Xe máy dung tích xi lanh trên 50 cm³ (Sê-ri ${series || "mô tô"}).`;
    isTwoLine = true;
  } else if (/^[A-Z]$/.test(series)) {
    // 1 chữ cái -> Thường là ô tô
    if (series === "A") {
      vehicleCategory = "Xe ô tô con / Du lịch";
      vehicleDescription = "Xe ô tô chở người dưới 9 chỗ ngồi (Sê-ri A).";
    } else if (series === "B") {
      vehicleCategory = "Xe ô tô khách";
      vehicleDescription = "Xe chở người từ 9 chỗ ngồi trở lên (Sê-ri B).";
    } else if (series === "C") {
      vehicleCategory = "Xe ô tô tải / Bán tải";
      vehicleDescription = "Xe tải hàng hóa hoặc xe bán tải chở hàng (Sê-ri C).";
    } else if (series === "D") {
      vehicleCategory = "Xe ô tô tải Van / Bán tải 2 chỗ";
      vehicleDescription = "Xe van chở hàng cỡ nhỏ lưu thông đô thị (Sê-ri D).";
    } else {
      vehicleCategory = `Xe ô tô dân sự (Sê-ri ${series})`;
      vehicleDescription = `Ô tô đăng ký dân sự cơ quan/cá nhân lưu thông (Sê-ri ${series}).`;
    }
  } else if (series === "LD") {
    vehicleCategory = "Xe liên doanh";
    vehicleDescription = "Doanh nghiệp có vốn đầu tư nước ngoài (Liên doanh).";
  }

  // Xác định màu biển
  let colorType: "white" | "blue" | "yellow" | "red" = "white";
  let colorName = "Biển trắng (Dân sự)";
  let colorDescription = "Nền trắng, chữ và số màu đen. Cấp cho cá nhân và doanh nghiệp trong nước.";

  if (provCode === "80" || /^(80A|80B|80M)/.test(clean)) {
    colorType = "blue";
    colorName = "Biển xanh (Công vụ)";
    colorDescription = "Nền xanh dương, chữ trắng. Cấp cho cơ quan hành chính nhà nước, bộ ngành Trung ương.";
    vehicleCategory = "Xe công vụ nhà nước";
  } else if (/^[A-Z]E|LD-V/.test(series)) {
    colorType = "yellow";
    colorName = "Biển vàng (Vận tải)";
    colorDescription = "Nền vàng, chữ đen. Cấp cho phương tiện hoạt động kinh doanh vận tải đường bộ.";
  }

  return {
    rawPlate: raw,
    normalizedPlate: clean,
    line1: line1 || clean,
    line2: line2 || "",
    isTwoLine,
    provinceCode: provCode,
    provinceName: province.name,
    regionName: province.region,
    series,
    vehicleCategory,
    vehicleDescription,
    colorType,
    colorName,
    colorDescription,
    isValidFormat: Boolean(provCode && series),
  };
}
