import cv2
import os
import re

# 解析视频文件名的函数
def parse_video_filename(filename):
    # 预期格式: lX_tY_rW_bH_*.mp4
    # 提取 l, t, r, b 的值
    pattern = r'l(\d+)_t(\d+)_r(\d+)_b(\d+)_.*\.mp4'
    match = re.match(pattern, filename)
    if match:
        l = int(match.group(1))
        t = int(match.group(2))
        r = int(match.group(3))
        b = int(match.group(4))
        return {'filename': filename, 'l': l, 't': t, 'r': r, 'b': b}
    else:
        return None

# 获取视频列表及其屏幕区域的函数
def get_video_list(video_dir):
    video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
    videos = []
    for vf in video_files:
        video_info = parse_video_filename(vf)
        if video_info:
            videos.append(video_info)
    return videos

# 解析sequence.txt文件的函数
def parse_sequence_file(sequence_file):
    actions = []
    with open(sequence_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line == '':
                continue
            # 检查是否包含逗号
            if ',' in line:
                # 从最后一个逗号拆分
                parts = line.rsplit(',', 1)
                action_desc = parts[0].strip()
                timestamp_str = parts[1].strip()
            else:
                # 没有逗号，说明是时间戳，动作描述为空
                action_desc = ''
                timestamp_str = line.strip()
            # 尝试从action_desc中提取坐标
            coord_pattern = r'<[^>]*\((\d+),\s*(\d+)\)>'
            coord_match = re.search(coord_pattern, action_desc)
            if coord_match:
                x = int(coord_match.group(1))
                y = int(coord_match.group(2))
                coords = {'x': x, 'y': y}
                # 去掉坐标部分和尖括号的action_desc
                action_desc = re.sub(r'<([^>]+)\s*\(\d+,\s*\d+\)>', r'\1', action_desc).strip()
            else:
                coords = None
                # 去掉尖括号
                action_desc = action_desc.strip('<>')
            actions.append((timestamp_str, action_desc, coords))
    return actions

# 将时间戳字符串转换为秒的函数
def timestamp_to_seconds(timestamp_str):
    try:
        # 拆分时、分、秒和毫秒
        time_parts = timestamp_str.split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds_parts = time_parts[2].split('.')
        seconds = int(seconds_parts[0])
        if len(seconds_parts) > 1:
            milliseconds = int(seconds_parts[1].ljust(3, '0'))  # 确保毫秒有三位数
        else:
            milliseconds = 0
        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
        return total_seconds
    except Exception as e:
        print(f"解析时间戳出错：{timestamp_str}")
        return None

# 处理视频并保存截取的帧的函数
def process_videos(video_dir, sequence_file, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    actions = parse_sequence_file(sequence_file)
    videos_info = get_video_list(video_dir)
    if not videos_info:
        print("在目录中未找到有效的视频文件")
        return
    # 创建每个视频的 VideoCapture 对象，并获取帧率
    for video_info in videos_info:
        video_file = os.path.join(video_dir, video_info['filename'])
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            print(f"无法打开视频文件 {video_file}")
            continue
        video_info['cap'] = cap
        # 获取帧率
        fps = cap.get(cv2.CAP_PROP_FPS)
        video_info['fps'] = fps
        # 获取总帧数
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_info['frame_count'] = frame_count
    last_video = None
    default_video = None
    for video_info in videos_info:
        if video_info['filename'].startswith('l0_t0'):
            default_video = video_info
            break
    for idx, (timestamp_str, action_desc, coords) in enumerate(actions):
        # 将时间戳转换为秒
        timestamp_sec = timestamp_to_seconds(timestamp_str)
        if timestamp_sec is None:
            continue
        # 确定要使用的视频
        if coords:
            x = coords['x']
            y = coords['y']
            # 找到包含该坐标的屏幕区域对应的视频
            video_to_use = None
            for video_info in videos_info:
                if (video_info['l'] <= x < video_info['r']) and (video_info['t'] <= y < video_info['b']):
                    video_to_use = video_info
                    break
            if not video_to_use:
                print(f"无法找到包含坐标 ({x}, {y}) 的视频")
                continue
            last_video = video_to_use
        else:
            # 如果没有坐标，使用上一个视频
            if last_video:
                video_to_use = last_video
            elif default_video:
                video_to_use = default_video
            else:
                # 如果没有上一个视频，跳过该动作
                print(f"动作 '{action_desc}' 没有坐标且没有默认视频可用，跳过")
                continue
        # 获取帧率
        fps = video_to_use['fps']
        # 计算时间戳对应的帧号
        frame_number = int(timestamp_sec * fps)
        # 获取前3帧和当前帧的帧号列表
        frame_indices = [frame_number]
        # 遍历帧号列表，获取对应的帧
        for i, fn in enumerate(frame_indices):
            if fn < 0 or fn >= video_to_use['frame_count']:
                print(f"帧号 {fn} 超出范围，跳过")
                continue
            cap = video_to_use['cap']
            # 设置视频到指定帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, fn)
            ret, frame = cap.read()
            if not ret:
                print(f"无法读取视频 {video_to_use['filename']} 帧号 {fn}")
                continue
            # 不调整尺寸，保留原始分辨率
            # 保存帧
            output_filename = os.path.join(output_dir, f"frame_{idx:04d}.jpg")
            cv2.imwrite(output_filename, frame)
            print(f"已保存帧到 {output_filename}")
    # 释放所有的 VideoCapture 对象
    for video_info in videos_info:
        cap = video_info.get('cap')
        if cap:
            cap.release()

# 主程序
if __name__ == '__main__':
    video_dir = '.'   # 视频文件所在的目录
    sequence_file = 'sequence.txt'     # 输入的sequence文件路径
    output_dir = 'save_image'          # 输出图像的目录
    process_videos(video_dir, sequence_file, output_dir)