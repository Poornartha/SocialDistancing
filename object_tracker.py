from absl import flags
import sys
FLAGS = flags.FLAGS
FLAGS(sys.argv)

import time
import numpy as np
import cv2
import matplotlib.pyplot as plt

import tensorflow as tf
from yolov3_tf2.models import YoloV3
from yolov3_tf2.dataset import transform_images
from yolov3_tf2.utils import convert_boxes

from deep_sort import preprocessing
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from tools import generate_detections as gdet

from itertools import combinations
import math


def is_close(p1, p2):
    """
    # 1. Calculate Euclidean Distance between two points
    :param:
    p1, p2 = two points for calculating Euclidean Distance
    :return:
    dst = Euclidean Distance between two 2d points
    """
    dst = math.sqrt(p1**2 + p2**2)
    return dst 


def convertBack(x, y, w, h): 
    """
    # 2. Converts center coordinates to rectangle coordinates     
    :param:
    x, y = midpoint of bbox
    w, h = width, height of the bbox
    
    :return:
    xmin, ymin, xmax, ymax
    """
    xmin = int(round(x - (w / 2)))
    xmax = int(round(x + (w / 2)))
    ymin = int(round(y - (h / 2)))
    ymax = int(round(y + (h / 2)))
    return xmin, ymin, xmax, ymax


class_names = [c.strip() for c in open('./data/labels/coco.names').readlines()]
yolo = YoloV3(classes=len(class_names))
yolo.load_weights('./weights/yolov3.tf')

max_cosine_distance = 0.5
nn_budget = None
nms_max_overlap = 0.8

model_filename = 'model_data/mars-small128.pb'
encoder = gdet.create_box_encoder(model_filename, batch_size=1)
metric = nn_matching.NearestNeighborDistanceMetric('cosine', max_cosine_distance, nn_budget)
tracker = Tracker(metric)

vid = cv2.VideoCapture('./data/video/test6.mp4')

codec = cv2.VideoWriter_fourcc(*'XVID')
vid_fps =int(vid.get(cv2.CAP_PROP_FPS))
vid_width,vid_height = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH)), int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
out = cv2.VideoWriter('./data/video/results6.avi', codec, vid_fps, (vid_width, vid_height))

from _collections import deque
pts = [deque(maxlen=30) for _ in range(1000)]

counter = []
saved = dict()
to_save = dict()

while True:
    _, img = vid.read()
    _, img_copy = vid.read()
    if img is None:
        print('Completed')
        break


    img_in = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_in = tf.expand_dims(img_in, 0)
    img_in = transform_images(img_in, 416)

    t1 = time.time()

    boxes, scores, classes, nums = yolo.predict(img_in)

    classes = classes[0]
    names = []

    for i in range(len(classes)):
        names.append(class_names[int(classes[i])])
    names = np.array(names)
    converted_boxes = convert_boxes(img, boxes[0])
    features = encoder(img, converted_boxes)

    detections = [Detection(bbox, score, class_name, feature) for bbox, score, class_name, feature in
                  zip(converted_boxes, scores[0], names, features) if class_name == 'person']

    

    boxs = np.array([d.tlwh for d in detections])
    scores = np.array([d.confidence for d in detections])
    classes = np.array([d.class_name for d in detections])
    indices = preprocessing.non_max_suppression(boxs, classes, nms_max_overlap, scores)
    detections = [detections[i] for i in indices]

    tracker.predict()
    tracker.update(detections)

    cmap = plt.get_cmap('tab20b')
    colors = [cmap(i)[:3] for i in np.linspace(0,1,20)]

    current_count = int(0)
    centroid_dict = dict()
    objectId = 0

    for track in tracker.tracks:
        if not track.is_confirmed() or track.time_since_update >1:
            continue
        bbox = track.to_tlbr()
        class_name= track.get_class()
        color = colors[int(track.track_id) % len(colors)]
        color = [i * 255 for i in color]

        cv2.rectangle(img, (int(bbox[0]),int(bbox[1])), (int(bbox[2]),int(bbox[3])), color, 2)
        cv2.rectangle(img, (int(bbox[0]), int(bbox[1]-30)), (int(bbox[0])+(len(class_name)
                    +len(str(track.track_id)))*17, int(bbox[1])), color, -1)
        cv2.putText(img, class_name+"-"+str(track.track_id), (int(bbox[0]), int(bbox[1]-10)), 0, 0.75,
                    (255, 255, 255), 2)

        center = (int(((bbox[0]) + (bbox[2]))/2), int(((bbox[1])+(bbox[3]))/2))

        centroid_dict[objectId] = center

        pts[track.track_id].append(center)

        for j in range(1, len(pts[track.track_id])):
            if pts[track.track_id][j-1] is None or pts[track.track_id][j] is None:
                continue
            thickness = int(np.sqrt(64/float(j+1))*2)
            cv2.line(img, (pts[track.track_id][j-1]), (pts[track.track_id][j]), color, thickness)

        height, width, _ = img.shape
        cv2.line(img, (0, int(3*height/6+height/5)), (width, int(3*height/6+height/5)), (0, 255, 0), thickness=2)
        cv2.line(img, (0, int(3*height/6-height/3)), (width, int(3*height/6-height/3)), (0, 255, 0), thickness=2)

        center_y = int(((bbox[1])+(bbox[3]))/2)

        if center_y <= int(3*height/6+height/5) and center_y >= int(3*height/6-height/5):
            if class_name == 'person':
                counter.append(int(track.track_id))
                current_count += 1
                to_save[objectId] = int(bbox[0]),int(bbox[1]), int(bbox[2]), int(bbox[3])
        objectId += 1

    
    red_zone_list = []
    red_line_list = []
    for (id1, p1), (id2, p2) in combinations(centroid_dict.items(), 2):
        dx, dy = p1[0] - p2[0], p1[1] - p2[1]
        distance = is_close(dx, dy)
        if distance < 200.0:
            if id1 not in red_zone_list:
                red_zone_list.append(id1) 
                red_line_list.append(p1[0:2])
            if id2 not in red_zone_list:
                red_zone_list.append(id2)
                red_line_list.append(p2[0:2])
                
                if id1 in to_save and id1 not in saved:
                    b = to_save[id1]
                    x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
                    x_start = int(x1)
                    y_start = int(y1)
                    x_end = int(x2)
                    y_end = int(y2)
                    roi = img_copy[y_start:y_end, x_start:x_end]
                    cv2.imwrite("./data/capture/" + str(id1) + ".jpg", roi)
                    saved[id1] = True

                if id2 in to_save and id2 not in saved:
                    b = to_save[id2]
                    x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
                    x_start = int(x1)
                    y_start = int(y1)
                    x_end = int(x2)
                    y_end = int(y2)
                    roi = img_copy[y_start:y_end, x_start:x_end]
                    cv2.imwrite("./data/capture/" + str(id2) + ".jpg", roi)
                    saved[id2] = True

    risk = 0
    for check in range(0, len(red_line_list)-1):
        start_point = red_line_list[check] 
        end_point = red_line_list[check+1]
        check_line_x = abs(end_point[0] - start_point[0])
        check_line_y = abs(end_point[1] - start_point[1])
        if (check_line_x < 200) and (check_line_y < 200):
            cv2.line(img, start_point, end_point, (0, 0, 255), 2)
            risk += 1
    

    total_count = len(set(counter))
    cv2.putText(img, "Current Count: " + str(current_count), (0, 80), 0, 1, (0, 0, 255), 2)
    cv2.putText(img, "Total Count: " + str(total_count), (0,130), 0, 1, (0,0,255), 2)
    cv2.putText(img, "Risks: " + str(risk), (0,180), 0, 1, (0,0,255), 2)

    fps = 1./(time.time()-t1)
    cv2.putText(img, "FPS: {:.2f}".format(fps), (0,30), 0, 1, (0,0,255), 2)
    cv2.resizeWindow('output', 1024, 768)
    cv2.imshow('output', img)
    out.write(img)

    if cv2.waitKey(1) == ord('q'):
        break
vid.release()
out.release()
cv2.destroyAllWindows()