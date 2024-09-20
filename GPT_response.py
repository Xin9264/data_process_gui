import base64
import requests
import io
from PIL import Image


def gpt4_chat_2images(image1, image2, llm="gpt-4o-mini", max_tokens=100, temperature=0, stop=None, resolution="low", action=None):
    # OpenAI API Key
    api_key = 'please input your OPENAI api key here'
    prompt = f'''You are an AI assistant tasked with describing the actions and purposes in GUI video clips, where the actions in the images are produced by mouse and keyboard interactions.

Your mission is to understand what the user did by analyzing two screenshots—one taken before and one after the user’s action.

Please compare the two images carefully to determine the specific action the user performed, focusing on the action itself and the user’s intent rather than describing the visual changes.

You may also use the following record of mouse and keyboard actions to assist your analysis: {action}.

Please provide a detailed yet concise description (one or two sentences) of the user’s action, focusing on what they did and why, rather than explaining what visually changed in the images.

- If the user performed an action but there is no observable change in the images, mention the action they took (e.g., “The user clicked on the button, but no response occurred”).
- Pay close attention to the mouse position and nearby actions, as the action may have been performed near the cursor.
- Focus on what the user is doing, such as typing or clicking, and explain their purpose (e.g., searching for something, navigating to a section, or opening an application).
- Be mindful that the user might be using a Chinese input method when typing.
- If the user performed a click action, please identify specifically what they clicked on and the likely reason.
- If the user performed a double-click, analyze the mouse coordinates from {action} to determine the location of the double-click, and infer which application or folder was likely opened. Even if the `cmd` command window is present in the screenshots, assume the user did not interact with it unless there is clear evidence to suggest otherwise.
- Specifically identify what the user clicked on and the possible reason, based on the mouse's location and movement.
- Please ignore the `cmd` window in the image, it is not important.
- If the user dragged something, they might just be moving the window or timeline to another position.
- If the user is interacting with Adobe Premiere, and clicked on the timeline, they might be cutting or moving a clip, depending on the selected tool.

Examples of common Adobe Premiere shortcuts:
  - `Ctrl + S`: Save the project.
  - `Space`: Play or pause the timeline.
  - `C`: Select the razor tool to cut clips.
  - `V`: Switch to the selection tool.
  - `Ctrl + Z`: Undo the last action.
  - `I`: Mark in-point for a clip.
  - `O`: Mark out-point for a clip.

Examples of your response might include:

- The user scrolled down the document to read more content.
- The user clicked the “Save” button to save changes.
- The user is typing a query into the search bar.
- The user dragged the window from the top-left corner to the center of the screen.
- The user clicked the “Documents” folder in the “Import” window.
- The user double-clicked on a desktop icon, likely to open an application or folder, but no interaction occurred with the `cmd` window present in the screenshots.
- The user pressed `Space` in Adobe Premiere, likely to play or pause the timeline.
- The user clicked on the timeline in Adobe Premiere, likely to cut or move the video clip depending on the selected tool.

Each set of images contains only one action.
'''

    # Extract mouse coordinates if available in action
    mouse_x, mouse_y = None, None
    if action[1] is not None:
        mouse_x = action[1]['x']
        mouse_y = action[1]['y']

    def crop_image_to_mouse(image_path, mouse_x, mouse_y, width=960, height=512):
        image = Image.open(image_path)
        img_width, img_height = image.size

        # Calculate the cropping box
        left = mouse_x - width // 2
        top = mouse_y - height // 2
        right = mouse_x + width // 2
        bottom = mouse_y + height // 2

        # Adjust the cropping box to ensure it stays within image bounds
        if left < 0:
            left = 0
            right = min(width, img_width)
        if right > img_width:
            right = img_width
            left = max(0, img_width - width)
        if top < 0:
            top = 0
            bottom = min(height, img_height)
        if bottom > img_height:
            bottom = img_height
            top = max(0, img_height - height)

        # Crop the image with the adjusted box
        cropped_image = image.crop((left, top, right, bottom))
        return cropped_image
    
    # Encode the image to base64
    def crop_image_to_mouse(image, mouse_x, mouse_y, width=1024, height=684):
        img_width, img_height = image.size

        # Calculate the cropping box
        left = mouse_x - width // 2
        top = mouse_y - height // 2
        right = mouse_x + width // 2
        bottom = mouse_y + height // 2

        # Adjust the cropping box to ensure it stays within image bounds
        if left < 0:
            left = 0
            right = min(width, img_width)
        if right > img_width:
            right = img_width
            left = max(0, img_width - width)
        if top < 0:
            top = 0
            bottom = min(height, img_height)
        if bottom > img_height:
            bottom = img_height
            top = max(0, img_height - height)

        # Crop the image with the adjusted box
        cropped_image = image.crop((left, top, right, bottom))
        return cropped_image
    
    # Encode the image to base64
    def encode_image(image):
        # Convert image object to bytes and then to base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Crop the images around the mouse if coordinates are provided
    if mouse_x and mouse_y:
        cropped_image1 = crop_image_to_mouse(image1, mouse_x, mouse_y)
        cropped_image2 = crop_image_to_mouse(image2, mouse_x, mouse_y)
    else:
        cropped_image1 = image1  # Use the full image if no coordinates
        cropped_image2 = image2

    base64_image1 = encode_image(cropped_image1)
    base64_image2 = encode_image(cropped_image2)

    # Create headers for OpenAI API
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
    "model": llm,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image1}",
                        "detail": resolution
                    },
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image2}",
                        "detail": resolution
                    },
                },
            ]
        }
    ],
    
    "max_tokens": max_tokens,
    "temperature": temperature
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    print(response.json())
    return response.json()['choices'][0]['message']['content']

