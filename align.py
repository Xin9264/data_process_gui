import cv2
from datetime import datetime, timedelta
import os
# from dect_frame import find_key_frame
import glob
import numpy as np

def find_key_frame(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(fps * 100)  # 读取前100秒
    frame_count = 0

    # 定义目标颜色 (BGR格式)
    target_color = np.array([231, 216, 173])  # 注意顺序是 BGR
    tolerance = 30  # 允许的颜色误差范围

    # 定义检测区域 (屏幕中心往上50像素为中心的20x20区域)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    center_x = frame_width // 2
    center_y = frame_height // 2 - 100
    check_region = (slice(center_y - 10, center_y + 10), slice(center_x - 10, center_x + 10))

    block_present = False  # 假设色块最初是不存在的
    appearance_frame = None
    disappearance_frame = None

    for i in range(total_frames):
        ret, current_frame = cap.read()
        if not ret:
            break
        
        frame_count += 1

        # 提取检测区域
        region = current_frame[check_region]

        # 计算区域的平均颜色
        average_color = region.mean(axis=(0, 1)).astype(int)

        # 检查平均颜色是否在目标颜色范围内
        if not block_present and np.all(np.abs(average_color - target_color) <= tolerance):
            # 色块首次出现
            block_present = True
            appearance_frame = frame_count
            print(f"色块首次出现于第 {appearance_frame} 帧")
        
        elif block_present and not np.all(np.abs(average_color - target_color) <= tolerance):
            # 色块消失
            block_present = False
            disappearance_frame = frame_count - 1
            print(f"色块消失在第 {disappearance_frame} 帧")
            break

    if disappearance_frame is None:
        if block_present:
            print("色块未在检测范围内消失")
        else:
            print("色块未出现在检测范围内")

    cap.release()
    return disappearance_frame

def convert_to_relative_time(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    base_time = None
    relative_lines = []
    ctrl_time = None

    for line in lines:
        if not line.strip():
            continue

        timestamp_str = line.split()[1]
        timestamp = datetime.strptime(timestamp_str, '%H:%M:%S.%f')

        if base_time is None:
            base_time = timestamp

        relative_time = (timestamp - base_time).total_seconds()
        
        if "<Ctrl>" in line and ctrl_time is None:
            ctrl_time = relative_time

        relative_timestamp_str = (datetime.min + timedelta(seconds=relative_time)).time().strftime('%H:%M:%S.%f')[:-3]
        relative_line = line.replace(timestamp_str, relative_timestamp_str)
        relative_lines.append(relative_line)

    new_file_path = file_path.replace('.txt', '_relative.txt')
    with open(new_file_path, 'w') as new_file:
        new_file.writelines(relative_lines)

    print(f"Relative time file saved as {new_file_path}")
    return new_file_path, ctrl_time

def adjust_timestamps(file_path, offset):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    adjusted_lines = []

    for line in lines[1:]:
        if not line.strip():
            continue

        timestamp_str = line.split()[1]
        timestamp = datetime.strptime(timestamp_str, '%H:%M:%S.%f')

        # 将时间戳转换为毫秒数
        timestamp_ms = timestamp.hour * 3600000 + timestamp.minute * 60000 + timestamp.second * 1000 + timestamp.microsecond / 1000

        if timestamp_ms > offset:
            adjusted_timestamp = timestamp - timedelta(milliseconds=offset)
            adjusted_timestamp_str = adjusted_timestamp.time().strftime('%H:%M:%S.%f')[:-3]
            adjusted_line = line.replace(timestamp_str, adjusted_timestamp_str)
            adjusted_lines.append(adjusted_line)


    new_file_path = file_path.replace('_relative.txt', '_adjusted.txt')
    with open(new_file_path, 'w') as new_file:
        new_file.writelines(adjusted_lines)

    print(f"Adjusted time file saved as {new_file_path}")
    return new_file_path

# 解析操作日志文件
def parse_log(log_path):
    actions = []
    with open(log_path, "r") as f:
        for line in f:
            parts = line.strip().split(" ")
            if len(parts) >= 3:
                _, time, *action_parts = parts
                timestamp = datetime.strptime(time, "%H:%M:%S.%f")
                action = " ".join(action_parts)
                actions.append((timestamp, action))
    return actions



def generate_subtitles_and_sequence(video_path, actions, output_file, sequence_file):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return
    
    subtitles = []
    sequence = []
    i = 0
    subtitle_index = 1
    
    while i < len(actions) - 1:
        timestamp, action = actions[i]

        if action == "HEARTBEAT":
            i += 1
            continue

        if i == 0:
            before_time = (timestamp - timedelta(milliseconds=150)).time()
        else:
            midpoint = (actions[i - 1][0] + (actions[i][0] - actions[i - 1][0]) / 2).time()
            before_time = max(midpoint, (actions[i][0] - timedelta(milliseconds=150)).time())

        # 合并连续键入
        if len(action) == 1:
            word = action
            while i < len(actions) - 1 and len(actions[i+1][1]) == 1:
                word += actions[i+1][1]
                i += 1
            if word:
                action = f"<Type '{word}'>"

        # 处理连续删除
        if action == "<Backspace>":
            while i < len(actions) - 1 and actions[i+1][1] == "<Backspace>":
                i += 1
            action = "<Backspace>"
        
        # 处理拖拽
        if i < len(actions) - 1 and action.startswith("<LButtonDown") and actions[i+1][1].startswith("<LButtonUp"):
            # 提取第一个操作的坐标
            coordinate1 = tuple(map(int, action.split("(")[1].split(")")[0].split(", ")))
            # 提取第二个操作的坐标
            coordinate2 = tuple(map(int, actions[i+1][1].split("(")[1].split(")")[0].split(", ")))
            i += 1
            action = f"<Drag From {coordinate1} To {coordinate2}>"

        # 处理鼠标点击
        if i < len(actions) - 1 and ((action.startswith("<LButtonDown") and (actions[i+1][1].startswith("<LClick") or actions[i+1][1].startswith("<LDblClick"))) or (action.startswith("<RButtonDown") and (actions[i+1][1].startswith("<RClick") or actions[i+1][1].startswith("<RDblClick")))):
            # 提取第一个操作的坐标
            coordinate1 = tuple(map(int, action.split("(")[1].split(")")[0].split(", ")))
            # 提取第二个操作的坐标
            coordinate2 = tuple(map(int, actions[i+1][1].split("(")[1].split(")")[0].split(", ")))
            if coordinate1 == coordinate2:
                i += 1
                action = actions[i][1]
        
        if i == len(actions) - 1:
            after_time = actions[i][0].time()
        else:
            midpoint = (actions[i][0] + (actions[i+1][0] - actions[i][0]) / 2).time()
            after_time = max(midpoint, (actions[i+1][0] - timedelta(milliseconds=150)).time())  
    
        i += 1
        
        # 生成字幕条目
        start_time = datetime.combine(datetime.min, before_time).strftime('%H:%M:%S,%f')[:-3]
        end_time = datetime.combine(datetime.min, after_time).strftime('%H:%M:%S,%f')[:-3]
        subtitle_entry = f"{subtitle_index}\n{start_time} --> {end_time}\n{action}\n"
        subtitles.append(subtitle_entry)
        subtitle_index += 1

        if sequence == []:
            sequence.append(f"{before_time.strftime('%H:%M:%S.%f')[:-3]}\n{action}, {after_time.strftime('%H:%M:%S.%f')[:-3]}\n")
        else:
            sequence.append(f"{action}, {after_time.strftime('%H:%M:%S.%f')[:-3]}\n")

    # 写入字幕文件
    with open(output_file, 'w') as f:
        f.writelines(subtitles)
    
    # 写入序列文件
    with open(sequence_file, 'w') as f:
        f.writelines(sequence)
    
    cap.release()
    print(f"Subtitles file saved as {output_file}")
    print(f"Sequence file saved as {sequence_file}")

def process_folder(folder_path):
    print("Now processing folder :", folder_path)

    video_files = glob.glob(os.path.join(folder_path, "*.mp4")) + glob.glob(os.path.join(folder_path, "*.mkv"))
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))

    if not video_files or not txt_files:
        print(f"No video or txt files found in {folder_path}")
        return

    video_path = video_files[0]
    print(video_path)
    log_path = txt_files[0]
    # output_dir = folder_path.replace("5003/siyuan", "5003/output/siyuan")
    output_dir = folder_path
    os.makedirs(output_dir, exist_ok=True)

    relative_log_path, ctrl_time = convert_to_relative_time(log_path)

    key_frame = find_key_frame(video_path=video_path)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print("fps:", fps)

    if ctrl_time is not None:
        t1 = ctrl_time * 1000  # Convert to milliseconds
        key_frame_time = key_frame / fps * 1000  # Convert frame number to milliseconds
        OFFSET = t1 - key_frame_time
        print(f"Calculated OFFSET: {OFFSET} ms")

        adjusted_log_path = adjust_timestamps(relative_log_path, OFFSET)

        actions = parse_log(adjusted_log_path)
        generate_subtitles_and_sequence(video_path, actions, os.path.join(output_dir, "subtitles.srt"), os.path.join(output_dir, "sequence.txt"))

    else:
        print("No <Ctrl> action found in the log file.")


if __name__ == "__main__":
    base_folder = "./Pikalab/save"
    subfolders = [f.path for f in os.scandir(base_folder) if f.is_dir()]

    for folder in subfolders:
        process_folder(folder)
