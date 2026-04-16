Checklist câu hỏi cần làm rõ trước khi thiết kế chi tiết
Tôi sẽ nhóm các câu hỏi theo từng hệ con. Với mỗi câu, tôi giải thích ngắn vì sao nó quan trọng — tức là câu trả lời sẽ đổi hướng giải ra sao. Đây chính là tinh thần "làm rõ problem" trong tài liệu của bạn.
1. Quy mô & Hiệu năng — đặt nền cho mọi quyết định
Bao nhiêu user tổng? Bao nhiêu concurrent online ở peak? 
Dưới 1k user. Online đồng thời dưới 1k
Ước lượng lượng tin nhắn mỗi ngày? → 
Tầm 4k tin nhắn 1 ngày
Nhóm chat có tối đa bao nhiêu thành viên? → 
Tối đa 50 thành viên
Deploy ở đâu? 1 region hay nhiều region? → 
Deploy khu vực máy chủ singapo, 1 máy chủ
2. Authentication — quyết định flow cơ bản
OAuth2 dùng provider nào? → google firebase authentication
User có thể đăng ký bằng email/password VÀ link OAuth cùng lúc không? → 
Có
Access token sống bao lâu? Có refresh token không? → 
access token 1h, refresh token 7 ngày
JWT lưu ở đâu phía client? → 
V1: dùng localstorage
V2: Tìm hiểu cách bảo mật hơn mà các công ty lớn dùng
Khi user đổi password/logout, các phiên WebSocket đang mở xử lý thế nào? → 
Logout hết rồi cho đăng nhập lại, các phiên và token cũ force hủy
Có cần 2FA không? Có cần "remember me" không? Có cần quên mật khẩu không? → 
V1 chưa cần
V2 dùng sau
3. User & Profile — ảnh hưởng đến quan hệ dữ liệu
Có chức năng kết bạn không? Hay ai cũng có thể chat với ai? → 
Ai cũng có thể chat
Có chức năng block user không? → 
Có
Username có đổi được không? Email có đổi được không? → 
Username có thể đổi nhưng hạn chế 60 ngày 1 lần, email không đổi
Profile có public/private không? Ai xem được thông tin của ai? → 
Ai xem cũng được
Có avatar không? Lưu ở đâu? → 
Có avatar, ban đầu lưu vào media server, sau lưu vào s3
4. Conversation & Group — phần dễ sai nhất
Chat 1-1: nếu A và B đã từng chat, rồi B "xóa cuộc trò chuyện" thì sao? → 
Ẩn về phía mình
Khi tạo chat 1-1 giữa A và B, có tạo conversation mới mỗi lần, hay luôn reuse conversation cũ? → 
Reuse lại conversation cũ
Tạo nhóm: ai tạo ra là owner. Owner có thể chuyển quyền không? Owner rời nhóm thì sao? → 
Owner có chuyển quyền. khi rời nhóm thì chuyển quyền cho người có thời gian vào thứ 2 sau owner , nếu trùng lặp thời gian vào thì xét từ trên xuống lấy 1 người. Nếu nhóm rời hết không còn ai thì xóa hết dữ liệu nhóm
Có bao nhiêu cấp quyền trong nhóm? → 
Admin và member. Admin được phép xóa người khác, còn member thì không. CÒn thêm thì ai thêm cũng được
Khi bị kick khỏi nhóm, user có xem lại được tin nhắn cũ không? Có thấy tin nhắn mới sau khi bị kick không? → 
Có user sẽ xem được tin nhắn cũ và 1 thông báo từ hệ thống nhóm về lý do rời nhóm: “Bạn đã rời nhóm” , “Bạn đã bị admin xóa khỏi nhóm"
Có invite link không? Có approval khi xin vào nhóm không? →
Không có, thêm là vào luôn
Có giới hạn số nhóm mỗi user tham gia không? → 
Tối đa 50 người
5. Messages — đa dạng hơn bạn tưởng
Tin nhắn có edit được không? Xóa được không? → Edit → cần lưu updated_at và có thể cả edit_history. Xóa → xóa thật hay soft delete (hiện "tin nhắn đã bị xóa")? 
Tin nhắn chỉ được sửa trong 24h. Nếu xóa thì xóa thật, phần tin nhắn reply của tin nhắn đó thì hiển thị tin nhắn không tồn tại
Có reply/quote tin nhắn khác không? → 
Có reply tin nhắn khác
Có forward tin nhắn không? → 
Đơn giản copy content
Có reaction (emoji) không? → 
Có reaction
Có đánh dấu đã đọc / trạng thái sent-delivered-read không? → 
Có đánh dấu đã đọc
Có typing indicator ("đang nhập...") không? → 
Có typing đang nhập
Có tin nhắn ghim (pin) không? Tin nhắn hệ thống ("A đã thêm B vào nhóm") không? → 
Có ghim tin nhắn của người dùng. Và có tin nhắn từ hệ thống
Tin nhắn có tìm kiếm full-text không? → 
Có tìm kiếm tin nhắn
Có giới hạn độ dài tin nhắn không? → 
Có giới hạn độ dài. Nếu quá độ dài thì chuyển sang tin nhắn tiếp theo
6. File & Ảnh — nhiều bẫy hơn bạn nghĩ
Giới hạn dung lượng mỗi file? Mỗi user mỗi tháng? → 
Giới hạn file ảnh và file là 20mb. Ảnh gửi tối đa 5 ảnh, file thì mỗi lần 1 file
Cho phép loại file nào? Block loại nào? → 
V1 Hiện tại file nào cũng được
Nice to have V1: Virus scan
V2: .exe, .bat thường bị block. Cần virus scan
Upload trực tiếp lên server hay upload lên S3 qua pre-signed URL? → 
V1 Upload lên server
V2 Qua S3
Ảnh có cần resize/thumbnail không? → 
V1: Nếu resize có làm ảnh nhẹ hơn không, Nếu có thì nên resize. Có thêm title ảnh là "image not found" nếu lỗi
V2: sử dụng cloudinary
Video có cần transcode không? Có cho phép video không? →
Không có upvideo, nếu là video thì vào dạng file
File có hết hạn không? (ví dụ: xóa sau 30 ngày) → 
Có hết hạn và xóa sau 30 ngày
Ai có quyền xem file? Link file có public không? → 
public
Link preview (Open Graph): có tự fetch metadata khi user gửi URL không? → 
Có → cần service riêng fetch + cache metadata. Không → chỉ hiển thị URL thuần.
7. Realtime & Socket — phần dễ over-engineer
Dùng Socket.IO, native WebSocket, hay SSE? → 
Dùng JAVA chat socket
Khi mất kết nối rồi kết nối lại, làm sao biết có tin nhắn nào bị miss? → 
Cần cơ chế "gửi lại tin từ timestamp X" khi reconnect. Thiếu cái này = user mất tin nhắn.
User mở nhiều tab/device thì sao? → 
Một user có nhiều socket connection. Phải push tất cả, và sync trạng thái read giữa các device.
Khi scale nhiều socket server, user A ở server 1, user B ở server 2 — làm sao deliver? → 
Redis pub/sub. Chưa cần ngay, nhưng phải thiết kế code sao cho dễ thêm vào.
8. Notification khi offline
Có push notification không? Qua kênh nào? → FCM cho web/mobile, APNs cho iOS native, email fallback. Mỗi kênh là một tích hợp riêng.
User tắt thông báo riêng cho từng nhóm được không? Mute trong X giờ được không? → Nếu có, cần bảng notification_settings per user per conversation.
Badge count (số tin chưa đọc) tính thế nào? → Redis cache vs query real-time. Với quy mô lớn, bắt buộc Redis.
"Do not disturb" theo giờ? → Nếu có, thêm phức tạp lớn cho dispatcher.
9. Bảo mật & Quyền riêng tư
Tin nhắn có mã hóa end-to-end không? → E2E encryption là dự án riêng, cực phức tạp. 99% khả năng bạn không cần. Nhưng phải chốt từ đầu vì nó ảnh hưởng toàn bộ kiến trúc (server không đọc được nội dung → không thể search, không thể preview, không thể gửi notification có nội dung).
Rate limiting: giới hạn tin nhắn/giây, login attempt, file upload? → Không có = dễ bị spam/DDoS.
Có cần audit log không? (ai đã vào nhóm nào, ai đã xóa ai) → Thêm bảng audit_logs. Quan trọng cho app doanh nghiệp.
GDPR / quyền xóa tài khoản: khi user xóa account, tin nhắn của họ xử lý thế nào? → Xóa hết (người khác thấy "tin nhắn đã bị xóa") hay giữ lại (chỉ ẩn tên)? Đây là quyết định pháp lý + sản phẩm.
10. Vận hành & Triển khai
Ngân sách hạ tầng mỗi tháng? → Quyết định được dùng managed service (RDS, Cloudinary, Pusher) hay self-host tất cả.
Đội ngũ có bao nhiêu người? Có DevOps riêng không? → Một mình → chọn stack đơn giản, ít service. Có đội → có thể phức tạp hơn.
Có CI/CD chưa? Staging environment không? → Ảnh hưởng đến tốc độ deploy và độ an toàn khi thay đổi.
Backup & disaster recovery? → Mất tin nhắn là thảm họa với app chat. Cần chính sách backup rõ ràng ngay từ đầu.
Monitoring & logging? → Sentry cho error, Prometheus/Grafana cho metrics, log tập trung. Thiếu = debug production như đi trong bóng tối.

