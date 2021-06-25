Pedestrian Detection and Tracking using YoloV3 and DeepSort
<br>
Installation Details: <br>

```
# Tensorflow CPU

conda env create -f conda-cpu.yml
conda activate tracker-cpu

# Tensorflow GPU

conda env create -f conda-gpu.yml
conda activate tracker-gpu
```

Downloading Weights <br>

```

# yolov3

wget https://pjreddie.com/media/files/yolov3.weights -O weights/yolov3.weights

# yolov3-tiny

wget https://pjreddie.com/media/files/yolov3-tiny.weights -O weights/yolov3-tiny.weights

# Place the Weights in the weights folder

```

<br> Convert the Weights in TF Weights <br>

```

python convert.py

```

<br>

Run:<br>

```
# For Video (Change the Location of the source video in object_tracker.py)

python object_tracker.py

# For Webcam

python webcam.py

```
