"""
process_video
----------------
This script represents the main program loop for the targetmarker detection.
It implements the logic for handling different videos as well as dealing with duplicate detections, the creation of new targetmarkers
and finally the drawing functionalities. 
The script allows for the automatic detection of various targetmarkers and length scales as well as their output. It was designed for my 
project and bachelor thesis and relies on different other modules to perform the aforementioned tasks.

@author: Daniel Gierse
"""


import warnings
warnings.filterwarnings('ignore')

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
import tensorflow.keras as tfk
import cv2 as cv
from os import listdir
from os.path import isfile, join
import argparse
import numpy as np
import time
import sys
from targetmarker import Targetmarker
import helpertools as htools
import scipy.stats as stats
import logging, sys



"""
"" Suppress tensorflow warnings
"""
# tf.logging.set_verbosity(tf.compat.v1.logging.ERROR)
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)


"""
This methods helps with the detection and creation of new targetmarkers. It takes the currently active markers (.is_active property
in targetmarker class) and checks their bounding boxes against the newly detected ones. If RoI > threshold => duplicate
If that duplicate has gotten a higher score from the Faster-RCNN than the other one: -> set new bounding box with those coords for the
marker in question.
This function also handles the creation of new targetmarkers,

"""            
def get_new_detections(frame,frame_id,tm_changebbox,target_result_bboxes,rcnn_scores,label_id,frame_width,frame_height,all_targetmarker_list,active_targetmarker_list,current_active_targetmarker_list):
    no_duplicate_bboxes_list = []
    succ = False
    
    if not len(target_result_bboxes) > 0:
        return succ,no_duplicate_bboxes_list, active_targetmarker_list, all_targetmarker_list, current_active_targetmarker_list
        
    if label_id == 3:
        duplicate_iou_threshold = tracker_iou_threshold_mxtdot
    else:
        duplicate_iou_threshold = tracker_iou_threshold_quad
    
    
    for detection_id,bbox in enumerate(target_result_bboxes):
        is_duplicate = False
        
        rcnn_score = rcnn_scores[detection_id]
        bboxcv2 = htools.convert_coords_tf_to_cv2(bbox,frame_width,frame_height)
        
        if Targetmarker.min_area_threshold > 0 and bboxcv2[2]*bboxcv2[3] < Targetmarker.min_area_threshold:
            continue

        #
        # iterates across all active targetmarkers (determined by the tracker.update() function) and checks whether or not a newly detected
        # marker has IoU with already known marker. If thats the case -> duplicate
        #                                           If new detection score > old detection score -> change_bounding_box of marker
        #
        # confirm() marker (for frequency filtering)
        for tm in current_active_targetmarker_list:
            is_duplicate = False                                                                
            if htools.calc_iou_cv2(bboxcv2,tm.bboxes_cv2[-1],duplicate_iou_threshold)[0]:
                if rcnn_score > tm.initial_rcnn_scores[-1]: 
                    tm_changebbox.append([frame_id,tm.initial_rcnn_scores[-1],rcnn_score])
                    tm.change_bounding_box(frame,bboxcv2,rcnn_score,frame_id,label_id)
                    
                tm.confirm()

                rcnn_score = target_result_bboxes[detection_id]
                
                is_duplicate = True
                break
            
        if is_duplicate:
            continue
        
        succ = True
        no_duplicate_bboxes_list.append(bboxcv2)
        
        #
        # create new marker since it is unknown yet 
        temp_marker = Targetmarker(current_frame_normalized, frame_id, mxtdot_model, bboxcv2, target_region, "cv2", label_id, confirm_delta_thresh=tm_confirm_delta_thresh, num_bnn_samples=tm_num_bnn_forward_passes, bnn_resize_size=tm_bnn_resize_size, output_folder=output_mxtdot_plot_folder,video_id=video_id,initial_rcnn_score=rcnn_score,minimum_type_decision_steps_threshold=tm_minimum_type_decision_steps_threshold,maximum_type_decision_steps_threshold=tm_maximum_type_decision_steps_threshold)
        all_targetmarker_list.append(temp_marker)
        active_targetmarker_list.append(temp_marker)
        current_active_targetmarker_list.append(temp_marker)
        
    return succ, no_duplicate_bboxes_list, active_targetmarker_list, all_targetmarker_list, current_active_targetmarker_list
    



input_directories = []
cwd = os.getcwd()

# handles the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", nargs='+', type=str,
                help="path to input folder")
ap.add_argument("-o", "--output", type=str,
                help='path to output video (and log data) directory')
ap.add_argument("-m", "--models", type=str, help='path to models directory')
ap.add_argument("-g", "--frozengraph", type=str, help="path to frozengraph")

args, leftovers = ap.parse_known_args()

if args.input is not None:
    for input_dir in args.input:
        input_directories.append(input_dir.rstrip(os.sep))
    if len(input_directories) > 1:
        print("input directories: {}".format(input_directories))
    else:
        print("input directory: {}".format(input_directories))
else:
    input_directories = [join(cwd,"testvideos")]
    print("required argument missing: --input  -> quitting")
    quit

if args.output is not None:
        output_directory = args.output
#        outputDirRoot = args.output.rstrip(os.sep)
        if not os.path.exists(args.output):
            os.makedirs(args.output)
        print("output directory: {}".format(args.output))
        print()
else:
    output_directory = join(cwd,"output")
    print("required argument missing: --output -> quitting")
    quit
    
if args.models is not None:
    model_folder = args.models
    print("models_directory: {}\n".format(model_folder))
else:
    print("required argument missing: --models  -> quitting")
    quit

rcnn_mxt_threshold = 0.8
rcnn_dot_threshold = 0.8
rcnn_quad_threshold = 0.2

#sample_resize_width = 28
#sample_resize_height = 28
#sample_additional_width_factor = 0.4
#sample_additional_height_factor = 0.4

tracker_iou_threshold_mxtdot = 0.1  # 0.3
tracker_iou_threshold_quad = 0.1
preliminary_scale_check_frames = 5

#
# parameter for targetmarker class
tm_num_bnn_forward_passes = 15
tm_confirm_delta_thresh = 35 #55
tm_minimum_type_decision_steps_threshold = 3
tm_maximum_type_decision_steps_threshold = 10
tm_bnn_resize_size = 16

quadlabel = 2
mxtdotlabel = 3


suffixes = ['.avi','.AVI','.mp4']

model_folder = join(model_folder)

print("working directory: {}".format(cwd))
print("model_folder: {}".format(model_folder))
print()

#
#
# definition of different folders and detectors
logging.debug("mxtdot_model: {}".format(join(join(join(model_folder,"mxtdot/"),"saved_model"),"saved_model")))

output_mxtdot_plot_folder = join(output_directory,"bnn_plots")
mxtdot_model = tfk.models.load_model(join(join(model_folder,"mxtdot/"),"saved_model"))
marker_detector = htools.TFMarkerDetectorv3(join(model_folder,"targetmarker"), join(join(model_folder,"targetmarker"),"checkpoint"), join(join(model_folder,"targetmarker"),"testlabels_mscoco.pbtxt"), 'pipeline')

vid_ops = htools.VideoOperations()

for input_directory in input_directories:
    # reads the filenames from the given directory
    video_files = [f for f in listdir(input_directory) if isfile(join(input_directory, f)) and '.DS_Store' not in f]
    print()                                                 
    print ('found ' + str(len(video_files)) + ' files: ' + str(video_files))
    print()
    
    # loop over all found filenames
    for video_id,video_title_ext in enumerate(video_files):
        start_time = time.time()
        # put the relative filepath back together
        filename_in = join(input_directory,video_title_ext)

        suffix = "unknown"
        
        # check whether suffix/datatype is know
        for suf in suffixes:
            if suf in video_title_ext:
                video_title = video_title_ext.rstrip(suf)
                suffix = suf
                break
    
        if suffix == "unknown":
            print("Unknown suffix, skipping file")
            continue

        all_targetmarker_list = []
        active_targetmarker_list = []
        frame_id = 0
        
        tm_changebox = []
        #
        #
        # load video at frame 0 and get different parameters like width and height of frame
        if vid_ops.load_video(filename_in):
            frame_width = vid_ops.frame_width
            frame_height = vid_ops.frame_height

            target_region = [0, 0, frame_width, frame_height]
            scale_target_region = [0, 0, frame_width, frame_height]
            
            print("-----------------------------------")
            print("file: {}".format(video_title_ext))  
            print("resolution: {}x{}".format(frame_width,frame_height))
            print("length: {} frames".format(vid_ops.length_in_frames))
            print()

            
         
            #
            #
            # get first frame in video
            get_frame_succ, current_frame, current_frame_normalized = vid_ops.get_frame()
            
            writer = cv.VideoWriter(join(output_directory, "{}_out{}".format(video_title,suffix)), cv.VideoWriter_fourcc('M','J','P','G'), 30, (frame_width,frame_height))
            
            #
            #
            # processing loop for each video. First the sliced target region is calculated, then scalereader is used on this sclice to 
            # find scale segments and calculate cm/pixel value. Afterwards every active targetmarker updates its tracker and get reaffirmed
            # on that list.
            # Then targetmarkers get detected by marker_detector and returned
            while get_frame_succ:
                current_frame_unmarked = current_frame_normalized.copy()
                
                start_time_frame = time.time()
                print("frame: {}".format(frame_id))
                current_detected_matches = []
                current_active_targetmarker_list = []

                for targetmarker in active_targetmarker_list:
                    targetmarker.update(current_frame,current_frame_normalized,frame_id)
                    if targetmarker.is_active:
                        current_active_targetmarker_list.append(targetmarker)


                mxt_succs, target_result_bboxes_mxt, scores_mxt, dot_succs, target_result_bboxes_dot, scores_dot, quad_succs, target_result_bboxes_quad, scores_quad,_ = marker_detector.detect(current_frame_normalized,min_detection_score_mxt=rcnn_mxt_threshold,min_detection_score_dot=rcnn_dot_threshold,min_detection_score_quad=rcnn_quad_threshold)
                
                mxt_new_det_succ, no_duplicate_bboxes_list_mxt, active_targetmarker_list, all_targetmarker_list, current_active_targetmarker_list = get_new_detections(current_frame_normalized,frame_id,tm_changebox,target_result_bboxes_mxt,scores_mxt,mxtdotlabel,frame_width,frame_height,all_targetmarker_list,active_targetmarker_list,current_active_targetmarker_list)
                dot_new_det_succ, no_duplicate_bboxes_list_dot, active_targetmarker_list, all_targetmarker_list, current_active_targetmarker_list = get_new_detections(current_frame_normalized,frame_id,tm_changebox,target_result_bboxes_dot,scores_dot,mxtdotlabel,frame_width,frame_height,all_targetmarker_list,active_targetmarker_list,current_active_targetmarker_list)
               
                for i,tm in enumerate(current_active_targetmarker_list):
                    centerpoint = (tm.centerpoints_abs[-1][0],tm.centerpoints_abs[-1][1])
                    current_frame = htools.draw_bounding_box(current_frame,tm.bboxes_cv2[-1],tm.printlabel,colorcode=tm.targetmarker_class_id)
                    current_frame = htools.draw_circle(current_frame,centerpoint[0],centerpoint[1],radius=3,colorcode=tm.targetmarker_class_id)
          
                
                current_frame = htools.draw_text(current_frame,5,80,400,len(current_active_targetmarker_list),rows=None,cols=None,section=None)
                
                active_targetmarker_list = current_active_targetmarker_list
                
                for tm in active_targetmarker_list:
                    tm.check_confirmation()
                    
                Targetmarker.on_frame_end()
                print("processing time: {} s".format(time.time()-start_time_frame))
                
                writer.write(current_frame)
                
                if frame_id % 10 == 0:
                    cv.imwrite(join(output_directory,"{}_{}.jpg".format(video_title,frame_id)), current_frame)
                    cv.imwrite(join(join(output_directory,"unmarked_images"),"{}_{}.jpg".format(video_title,frame_id)), current_frame_unmarked)
                
                get_frame_succ, current_frame, current_frame_normalized = vid_ops.get_frame()

                if get_frame_succ:
                    frame_id += 1
            
            #
            # close video writer
            writer.release()
            
            #
            # open new video writer to produce and save filtered output. Reiterates over the original video and draws saved values on frames.
            writer_clean = cv.VideoWriter(join(output_directory, "{}_out_filtered.{}".format(video_title,suffix)), cv.VideoWriter_fourcc('M','J','P','G'), 30, (frame_width,frame_height))
            
            vid_ops.restart_video()
            frame_id = 0
            get_frame_succ, current_frame, current_frame_normalized = vid_ops.get_frame()
            
            print()
            print("saving filtered video...")
            while get_frame_succ:
                current_marker_counter = 0
                for tm in all_targetmarker_list:
                    if tm.targetmarker_class_id == 12:
                        continue
                    if len(tm.bboxes_cv2) <= 11:
                        continue
                    if frame_id >= tm.start_frame_id and (frame_id - tm.start_frame_id) < len(tm.bboxes_cv2):
                        current_frame = htools.draw_bounding_box(current_frame,tm.bboxes_cv2[frame_id - tm.start_frame_id],tm.printlabel,colorcode=tm.targetmarker_class_id)                       
                        current_frame = htools.draw_circle(current_frame,tm.centerpoints_abs[frame_id - tm.start_frame_id][0],tm.centerpoints_abs[frame_id - tm.start_frame_id][1],radius=3,colorcode=tm.targetmarker_class_id)
                        
                        current_marker_counter += 1
                
                current_frame = htools.draw_text(current_frame,5,80,400,current_marker_counter,rows=None,cols=None,section=None)
                
                if frame_id % 10 == 0:
                    cv.imwrite(join(join(output_directory,"filtered_images"),"{}_{}.jpg".format(video_title,frame_id)), current_frame)
                    if frame_id % 50 == 0:
                        print("writing frame {}/{}".format(frame_id,vid_ops.length_in_frames))    
                
                writer_clean.write(current_frame)
                get_frame_succ, current_frame, current_frame_normalized = vid_ops.get_frame()
                if get_frame_succ:
                    frame_id += 1
            
            print("writing frame {}/{}".format(vid_ops.length_in_frames,vid_ops.length_in_frames))
            # close video writer
            writer_clean.release()

            Targetmarker.reset()
