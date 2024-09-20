from datetime import datetime, timedelta
import os
import glob
import re
import numpy as np
import cv2

def find_key_frame(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    # print(f"FPS: {fps}")
    total_frames = int(fps * 100) 
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

def parse_log(log_path, coordinate1, coordinate2):
    actions = []
    current_screen = 1

    left_1, top_1, right_1, bottom_1 = coordinate1
    left_2, top_2, right_2, bottom_2 = coordinate2

    with open(log_path, "r") as f:
        for line in f:
            parts = line.strip().split(" ")

            if len(parts) >= 3:
                _, time, *action_parts = parts
                timestamp = datetime.strptime(time, "%H:%M:%S.%f")
                action = " ".join(action_parts)

                # 使用正则表达式判断操作是否包含坐标
                match = re.search(r"\((\-?\d+),\s*(\-?\d+)\)", action)
                if match:
                    x, y = int(match.group(1)), int(match.group(2))
                    if left_1 <= x <= right_1 and top_1 <= y <= bottom_1:
                        current_screen = 1
                    elif left_2 <= x <= right_2 and top_2 <= y <= bottom_2:
                        current_screen = 2
                    
                actions.append([timestamp, action, current_screen])

    return actions

def adjust_timestamps(actions, offset1, offset2):
    for action in actions:
        if len(action) != 3:
            print(f"Unexpected action format: {action}")
            continue
        
        timestamp = action[0]

        timestamp_ms = timestamp.hour * 3600000 + timestamp.minute * 60000 + timestamp.second * 1000 + timestamp.microsecond / 1000

        if action[2] == 1:
            if timestamp_ms > offset1:
                adjusted_timestamp = timestamp - timedelta(milliseconds=offset1)
                action[0] = adjusted_timestamp
        else:
            if timestamp_ms > offset2:
                adjusted_timestamp = timestamp - timedelta(milliseconds=offset2)
                action[0] = adjusted_timestamp

    adjusted_log_path = "5003/adjusted_log.txt"
    with open(adjusted_log_path, 'w') as f:
        for action in actions:
            f.write(f"{action[0].strftime('%H:%M:%S.%f')} {action[1]} {action[2]}\n")

    return actions



def generate_subtitles_and_sequence(actions, output_file, sequence):
    # 写入字幕文件
    output_file_1 = output_file.replace(".srt", "_1.srt")
    output_file_2 = output_file.replace(".srt", "_2.srt")
    
    subtitles_1 = []
    subtitles_2 = []
    i = 0
    subtitle_1_index = 1
    subtitle_2_index = 1
    
    while i < len(actions) - 1:
        timestamp, action, _ = actions[i]

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
        
        
        # 生成字幕条目
        start_time = datetime.combine(datetime.min, before_time).strftime('%H:%M:%S,%f')[:-3]
        end_time = datetime.combine(datetime.min, after_time).strftime('%H:%M:%S,%f')[:-3]
        if actions[i][2] == 1:
            subtitle_entry = f"{subtitle_1_index}\n{start_time} --> {end_time}\n{action}\n\n"
            subtitles_1.append(subtitle_entry)
            subtitle_1_index += 1
        else:
            subtitle_entry = f"{subtitle_2_index}\n{start_time} --> {end_time}\n{action}\n\n"
            subtitles_2.append(subtitle_entry)
            subtitle_2_index += 1

        i += 1

        if sequence == []:
            sequence.append(f"{before_time.strftime('%H:%M:%S.%f')[:-3]}\n{action}, {after_time.strftime('%H:%M:%S.%f')[:-3]}\n")
        else:
            sequence.append(f"{action}, {after_time.strftime('%H:%M:%S.%f')[:-3]}\n")


    with open(output_file_1, 'w') as f1:
        f1.writelines(subtitles_1)

    with open(output_file_2, 'w') as f2:
        f2.writelines(subtitles_2)

    print(f"Subtitles file saved as {output_file_1} and {output_file_2}")

def extract_coordinates(video_path):
    # 提取文件名
    file_name = video_path.split('/')[-1]
    
    # 使用正则表达式提取坐标
    match = re.search(r'l(-?\d+)_t(-?\d+)_r(-?\d+)_b(-?\d+)', file_name)
    if match:
        left = int(match.group(1))
        top = int(match.group(2))
        right = int(match.group(3))
        bottom = int(match.group(4))
        return [left, top, right, bottom]
    else:
        return None

def judge_screen(video_path):
    try:
        coordinates = extract_coordinates(video_path)
        if coordinates:
            if coordinates[0] == 0 and coordinates[1] == 0:
                return 1
            else:
                return 2
    except Exception as e:
        print(f"Error: {e}")
        return 0

def process_folder(folder_path):
    print("Now processing folder :", folder_path)

    video_files = glob.glob(os.path.join(folder_path, "*.mp4")) + glob.glob(os.path.join(folder_path, "*.mkv"))
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))

    if not video_files or not txt_files:
        print(f"No video or txt files found in {folder_path}")
        return
    
    # 按文件名长度排序
    video_files.sort(key=lambda x: len(os.path.basename(x)))

    video_path_1 = video_files[0]
    video_path_2 = video_files[1]

    coordinate1 = extract_coordinates(video_path_1)
    coordinate2 = extract_coordinates(video_path_2)

    log_path = txt_files[0]
    # output_dir = folder_path.replace("5003/wangxin3", "5003/output/wangxin")
    output_dir = folder_path

    os.makedirs(output_dir, exist_ok=True)

    relative_log_path, ctrl_time = convert_to_relative_time(log_path)

    screen_1 = judge_screen(video_path_1)

    if screen_1 == 1:
        key_frame_1 = find_key_frame(video_path=video_path_1)
        key_frame_2 = find_key_frame(video_path=video_path_2)
    else:
        key_frame_1 = find_key_frame(video_path=video_path_2)
        key_frame_2 = find_key_frame(video_path=video_path_1)
    
    cap = cv2.VideoCapture(video_path_1)
    fps_1 = cap.get(cv2.CAP_PROP_FPS)
    print("fps_1:", fps_1)
    cap = cv2.VideoCapture(video_path_2)
    fps_2 = cap.get(cv2.CAP_PROP_FPS)
    print("fps_2:", fps_2)

    if ctrl_time is not None:
        t1 = ctrl_time * 1000  # Convert to milliseconds
        key_frame_time_1 = key_frame_1 / fps_1 * 1000  # Convert frame number to milliseconds
        key_frame_time_2 = key_frame_2 / fps_2 * 1000  # Convert frame number to milliseconds
        OFFSET_1 = t1 - key_frame_time_1
        OFFSET_2 = t1 - key_frame_time_2
        print(f"Calculated OFFSET_1: {OFFSET_1} ms")
        print(f"Calculated OFFSET_2: {OFFSET_2} ms")

        actions = parse_log(relative_log_path, coordinate1, coordinate2)

        adjust_timestamps(actions, OFFSET_1, OFFSET_2)

        sequence = []
        generate_subtitles_and_sequence(actions, os.path.join(output_dir, "subtitles.srt"), sequence)

        # 写入序列文件
        with open(os.path.join(output_dir, "sequence.txt"), 'w') as f:
            f.writelines(sequence)

    else:
        print("No <Ctrl> action found in the log file.")

if __name__ == "__main__":
    base_folder = "5003/test"
    subfolders = [f.path for f in os.scandir(base_folder) if f.is_dir()]

    for folder in subfolders:
        process_folder(folder)
