#!/usr/bin/env python
from __future__ import print_function, division
import rospy
import cv_bridge

from visualization_msgs.msg import Marker
from visualization_msgs.msg import MarkerArray
from hector_perception_msgs.msg import LocalizeBarsAction
from hector_perception_msgs.msg import LocalizeBarsResult
from sensor_msgs.msg import CameraInfo

from enum import Enum

import sensor_msgs.msg
import geometry_msgs.msg
import hector_perception_msgs.msg
import hector_nav_msgs.srv
import bar_detection
import actionlib
import numpy as np
import cv2
from image_geometry import PinholeCameraModel



class BarDetectionErrorType(Enum):
    NoError = 0
    NoImageError = 1
    ProjectPixelTo3DRayError = 2
    GetDistanceToObstacleError = 3
    NoIntersectionPointError = 4
    NoBarsDetected = 5


class BarDetectionError(Exception):
    def __init__(self, message, error):
        super(BarDetectionError, self).__init__(message)
        if not isinstance(error, BarDetectionErrorType):
            raise TypeError("Error must be set to a BarDetectionErrorType.")
        self.error = error


class BarDetectionNode:
    def __init__(self):
        # Localization Parameters
        self.number_line_points = 10

        # end of Localization Parameters

        self.last_front_image = None
        self.last_back_image = None
        self.bridge = cv_bridge.CvBridge()
        self.detector = bar_detection.BarDetection()
        self.detection_image_pub = rospy.Publisher("~detection_image", sensor_msgs.msg.Image, queue_size=10, latch=True)
        self.perception_pub = rospy.Publisher("image_percept", hector_perception_msgs.msg.PerceptionDataArray,
                                              queue_size=10)

        self.front_image_sub = rospy.Subscriber("~front_image", sensor_msgs.msg.Image, self.front_image_cb)
        self.back_image_sub = rospy.Subscriber("~back_image", sensor_msgs.msg.Image, self.back_image_cb)

        # Debug stuff
        self.detection_image_pub = rospy.Publisher("~detection_image", sensor_msgs.msg.Image, queue_size=10, latch=True)
        self.debug = rospy.get_param("~debug", False)
        self.debug_maker_pub = rospy.Publisher("~debug_marker", MarkerArray, queue_size=10)
        self.max_marker_count = 2

        # Action Server
        self.server = actionlib.SimpleActionServer("~run_detector", LocalizeBarsAction, self.execute_action, False)
        self.server.start()

        rospy.loginfo("Waiting for Camera info")
        camera_info = rospy.wait_for_message("~front_camera_info", CameraInfo)
        self.pinhole_camera_model = PinholeCameraModel()
        self.pinhole_camera_model.fromCameraInfo(camera_info)
        # Init Services
        #project_pixel_to_ray_srv = "project_pixel_to_ray"
        #rospy.loginfo("Waiting for service " + project_pixel_to_ray_srv)
        #rospy.wait_for_service(project_pixel_to_ray_srv)
        #self.project_pixel_to_ray = rospy.ServiceProxy(project_pixel_to_ray_srv,
        #                                               hector_perception_msgs.srv.ProjectPixelTo3DRay)
        get_distance_to_obstacle_srv = "/move_group/get_distance_to_obstacle"
        rospy.loginfo("Waiting for service " + get_distance_to_obstacle_srv)
        rospy.wait_for_service(get_distance_to_obstacle_srv)
        self.get_distance_to_obstacle = rospy.ServiceProxy(get_distance_to_obstacle_srv,
                                                           hector_nav_msgs.srv.GetDistanceToObstacle)
        rospy.loginfo("Found all services.")

    def front_image_cb(self, image):
        self.last_front_image = image

    def back_image_cb(self, image):
        self.last_back_image = image

    def execute_action(self, goal):
        img = self.last_front_image if goal.front_cam else self.last_back_image

        bar_localization, error, error_msg = self.run_localization(img)
        result = LocalizeBarsResult()
        result.success = error == BarDetectionErrorType.NoError
        result.error = error.value
        result.error_msg = error_msg
        result.pos = bar_localization

        self.server.set_succeeded(result)

    def run_localization(self, img):
        error = BarDetectionErrorType.NoError
        error_msg = ""
        bar_location = geometry_msgs.msg.PoseStamped()

        if img is not None:
            image_cv = self.bridge.imgmsg_to_cv2(img, desired_encoding="rgb8")
            detected_img, detections = self.detector.detect(image_cv)
            if len(detections) != 0:

                step_size_1 = detections[0].length / self.number_line_points
                step_size_2 = detections[1].length / self.number_line_points

                global_points1 = np.zeros((self.number_line_points, 3))
                global_points2 = np.zeros((self.number_line_points, 3))
                try:
                    for n in range(self.number_line_points):
                        global_points1[n, :] = self.get_global_point(detections[0].start + n * step_size_1 * detections[0].dir)
                        global_points2[n:, :] = self.get_global_point(detections[1].start + n * step_size_2 * detections[1].dir)
                except BarDetectionError as e:
                    return bar_location, e.error, e.message
                
                """
                global_points1 = np.zeros((detections[0].contour.shape[0], 3))
                global_points2 = np.zeros((detections[1].contour.shape[0], 3))

                for n in range(global_points1.shape[0]):
                    try:
                        global_points1[n, :] = self.get_global_point(detections[0].contour[n])
                    except BarDetectionError as e:
                        global_points1[n, :] = np.array([np.NAN, np.NAN, np.NAN])
                        continue

                for n in range(global_points2.shape[0]):
                    try:
                        global_points2[n, :] = self.get_global_point(detections[1].contour[n])
                    except BarDetectionError as e:
                        global_points2[n, :] = np.array([np.NAN, np.NAN, np.NAN])
                        continue
                global_points1 = global_points1[~np.all(global_points1 == np.NAN, axis=1)]
                global_points2 = global_points2[~np.all(global_points2 == np.NAN, axis=1)]

                """

                base1, dir1 = self.fit_line(global_points1)
                base2, dir2 = self.fit_line(global_points2)

                if self.debug:
                    detection_image_msg = self.bridge.cv2_to_imgmsg(detected_img, encoding="rgb8")
                    self.detection_image_pub.publish(detection_image_msg)
                    self.debug_add_marker(base1, dir1, base2, dir2)
            else:
                error_msg = "No bars detected"
                error = BarDetectionErrorType.NoBarsDetected
                if self.debug:
                    detection_image_msg = self.bridge.cv2_to_imgmsg(detected_img, encoding="rgb8")
                    self.detection_image_pub.publish(detection_image_msg)
        else:
            error_msg = "Detection skipped, because no image has been received yet."
            error = BarDetectionErrorType.NoImageError
            rospy.logwarn(error_msg)

        return bar_location, error, error_msg

    def get_global_point(self, image_point):
        point_msg = geometry_msgs.msg.PointStamped()
        point_msg.point.x = image_point[0]
        point_msg.point.y = image_point[1]

        try:
            #point_resp_project = self.project_pixel_to_ray(point_msg)
            point_resp_project = self.pinhole_camera_model.projectPixelTo3dRay(point_msg)
        except rospy.ServiceException as e:
            raise BarDetectionError("ProjectPixelTo3DRay Service Exception",
                                    BarDetectionErrorType.ProjectPixelTo3DRayError)
        try:
            point_resp_raycast = self.get_distance_to_obstacle(point_resp_project.ray)
        except rospy.ServiceException as e:
            raise BarDetectionError("GetDistanceToObstacle Service Exception",
                                    BarDetectionErrorType.GetDistanceToObstacleError)

        if point_resp_raycast.distance == -1:
            raise BarDetectionError("No intersection point found",
                                    BarDetectionErrorType.NoIntersectionPointError)

        global_point = point_resp_raycast.end_point.point
        return np.array([global_point.x, global_point.y, global_point.z])

    def fit_line(self, points):
        vx, vy, _, x, y, _ = cv2.fitLine(np.array(points), cv2.DIST_L2, 0, 0.01, 0.01)
        return np.array([x[0], y[0]]), np.array([vx[0], vy[0]])

    def debug_add_marker(self, base1, dir1, base2, dir2):

        points = [base1 + n * 0.1 * dir1 for n in range(-10, 10)]
        points.extend([base2 + n * 0.1 * dir2 for n in range(-10, 10)])
        marker_array = MarkerArray()
        for point, n in zip(points, range(len(points))):
            marker = Marker()
            marker.header.frame_id = "world"
            marker.id = n
            marker.type = marker.SPHERE
            marker.action = marker.ADD
            marker.scale.x = 0.05
            marker.scale.y = 0.05
            marker.scale.z = 0.05

            marker.color.a = 1.0
            marker.color.r = 1.0
            marker.color.g = 0.0
            marker.color.b = 0.0

            marker.pose.orientation.w = 1.0
            marker.pose.position.x = point[0]
            marker.pose.position.y = point[1]
            marker.pose.position.z = 0

            marker_array.markers.append(marker)
            self.debug_maker_pub.publish(marker_array)


if __name__ == "__main__":
    rospy.init_node("bar_detection")
    bar_detection = BarDetectionNode()
    rospy.spin()
