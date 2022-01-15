import cv2

def draw(dest_img, color, draw_func):
    rgb = (color[0], color[1], color[2])
    
    h, w, c = dest_img.shape
    img = dest_img
    if len(color) == 4:
        img = dest_img.copy()
    
    draw_func(img, rgb)
    
    if img is not dest_img:
        alpha = float(color[3]) / 255
        beta = 1.0 - alpha
        dest_img = cv2.addWeighted(dest_img, beta, img, alpha, 1.0)

    return dest_img
