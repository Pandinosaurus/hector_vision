#ifndef _HECTOR_HEAT_DETECTION_H_
#define _HECTOR_HEAT_DETECTION_H_

#include <ros/ros.h>

#include <std_msgs/String.h>
#include <hector_worldmodel_msgs/ImagePercept.h>
#include <image_transport/image_transport.h>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/features2d/features2d.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <sensor_msgs/image_encodings.h>
//#include <thermaleye_msgs/Mapping.h>
#include <message_filters/subscriber.h>
#include <message_filters/time_synchronizer.h>
#include <message_filters/sync_policies/approximate_time.h>

#include <dynamic_reconfigure/server.h>
#include <hector_heat_detection/HeatDetectionConfig.h>
//#include <argo_vision_msgs/GetMeasurement.h>

#include <std_msgs/Bool.h>

using hector_heat_detection::HeatDetectionConfig;

class HeatDetection{
public:
    HeatDetection(ros::NodeHandle& nh_,ros::NodeHandle& pnh_);
    ~HeatDetection();
private:

    void setProcessingEnabledCb(const std_msgs::Bool& msg);
    void publishProcessingEnabledState();

    void imageCallback(const sensor_msgs::ImageConstPtr& img, const sensor_msgs::CameraInfoConstPtr& info, const sensor_msgs::ImageConstPtr& img_mapped);
    //void mappingCallback(const thermaleye_msgs::Mapping& mapping);
    void dynRecParamCallback(HeatDetectionConfig &config, uint32_t level);
    //bool getMeasurementSrvCallback(argo_vision_msgs::GetMeasurement::Request &req,
    //                    argo_vision_msgs::GetMeasurement::Response &res);
    ros::Publisher pub_;
    image_transport::CameraSubscriber sub_;

    message_filters::Subscriber<sensor_msgs::Image> image_sub_;
    message_filters::Subscriber<sensor_msgs::CameraInfo> cam_info_sub_;

    message_filters::Subscriber<sensor_msgs::Image> image_mapped_sub_;

   typedef message_filters::sync_policies::ApproximateTime<sensor_msgs::Image, sensor_msgs::CameraInfo, sensor_msgs::Image> SyncPolicy;

   message_filters::Synchronizer<SyncPolicy> time_sync_;


  image_transport::CameraPublisher pub_detection_;
    ros::Subscriber sub_mapping_;

    ros::Publisher processing_enabled_pub_;
    ros::Subscriber processing_enabled_sub_;
    bool processing_enabled_;

    typedef dynamic_reconfigure::Server<HeatDetectionConfig> ReconfigureServer;
    boost::shared_ptr<ReconfigureServer> dyn_rec_server_;
    boost::recursive_mutex config_mutex_;

    bool mappingDefined_;
    bool perform_measurement_;

    double minTempVictim_;
    double maxTempVictim_;
    double minAreaVictim_;
    double minDistBetweenBlobs_;
    std::string perceptClassId_;

    //thermaleye_msgs::Mapping mapping_;
    double min_temp_img_;
    double max_temp_img_;

    double blob_temperature_;

    int image_count_ ;

    cv::Mat img_thres_min_;
    cv::Mat img_thres_max_;
    cv::Mat img_thres_;

    //ros::ServiceServer get_measurement_server_;


};

#endif
