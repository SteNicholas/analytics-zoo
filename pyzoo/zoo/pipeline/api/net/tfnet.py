#
# Copyright 2018 Analytics Zoo Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from bigdl.nn.layer import Layer

import numpy as np
import six
import tempfile
import os
import sys
from pyspark import RDD

from zoo.common.nncontext import getOrCreateSparkContext
from zoo.common import JTensor, Sample
from zoo.feature.image import ImageSet
from zoo.common.utils import callZooFunc
from zoo.pipeline.api.net.tf_dataset import TFImageDataset, TFDataset, MapDataset

if sys.version >= '3':
    long = int
    unicode = str


def to_sample_rdd(x, y, sc, num_slices=None):
    """
    Conver x and y into RDD[Sample]
    :param sc: SparkContext
    :param x: ndarray and the first dimension should be batch
    :param y: ndarray and the first dimension should be batch
    :param numSlices:
    :return:
    """
    x_rdd = sc.parallelize(x, num_slices)
    y_rdd = sc.parallelize(y, num_slices)
    return x_rdd.zip(y_rdd).map(lambda item: Sample.from_ndarray(item[0], item[1]))


class TFNet(Layer):
    def __init__(self, path, input_names=None, output_names=None,
                 tf_session_config=None, jvalue=None, bigdl_type="float"):

        if jvalue is not None:
            super(TFNet, self).__init__(jvalue, bigdl_type)
            return

        config_bytes = None
        if tf_session_config is not None:
            import tensorflow as tf
            assert isinstance(tf_session_config, tf.ConfigProto)
            tf_session_config.use_per_session_threads = True
            config_bytes = bytearray(tf_session_config.SerializeToString())
        if input_names is None and output_names is None:
            if tf_session_config is None:
                super(TFNet, self).__init__(None, bigdl_type,
                                            path)
            else:
                super(TFNet, self).__init__(None, bigdl_type,
                                            path, config_bytes)

        else:
            if isinstance(input_names, six.string_types):
                input_names = [input_names]
            if isinstance(output_names, six.string_types):
                output_names = [output_names]
            if tf_session_config is None:
                super(TFNet, self).__init__(None, bigdl_type,
                                            path,
                                            input_names,
                                            output_names)
            else:
                super(TFNet, self).__init__(None, bigdl_type,
                                            path,
                                            input_names,
                                            output_names, config_bytes)

    @staticmethod
    def check_input(input):
        """
        :param input: ndarray or list of ndarray or JTensor or list of JTensor.
        :return: (list of JTensor, isTable)
        """

        def to_jtensor(i):
            if isinstance(i, np.ndarray):
                return JTensor.from_ndarray(i)
            elif isinstance(i, JTensor):
                return i
            else:
                raise Exception("Error unknown input type %s" % type(i))

        if type(input) is list:
            if len(input) == 0:
                raise Exception('Error when checking: empty input')
            return list(map(lambda i: to_jtensor(i), input)), True
        else:
            return [to_jtensor(input)], False

    def predict(self, x, batch_per_thread=1, distributed=True, mini_batch=False):
        """
        Use a model to do prediction.
        """
        if isinstance(x, ImageSet):
            results = callZooFunc(self.bigdl_type, "zooPredict",
                                  self.value,
                                  x,
                                  batch_per_thread)
            return ImageSet(results)

        if isinstance(x, TFImageDataset):
            results = callZooFunc(self.bigdl_type, "zooPredict",
                                  self.value,
                                  x.get_prediction_data(),
                                  x.batch_per_thread)
            return ImageSet(results)

        if isinstance(x, MapDataset):
            raise ValueError("MapDataset is not supported in TFNet")

        if isinstance(x, TFDataset):
            results = callZooFunc(self.bigdl_type, "zooPredict",
                                  self.value,
                                  x.get_prediction_data())
            return results.map(lambda result: Layer.convert_output(result))

        if mini_batch:
            results = callZooFunc(self.bigdl_type, "zooPredict",
                                  self.value,
                                  x)
            return results.map(lambda result: Layer.convert_output(result))

        if distributed:
            if isinstance(x, np.ndarray):
                data_rdd = to_sample_rdd(x, np.zeros([x.shape[0]]), getOrCreateSparkContext())
            elif isinstance(x, RDD):
                data_rdd = x
            else:
                raise TypeError("Unsupported prediction data type: %s" % type(x))
            results = callZooFunc(self.bigdl_type, "zooPredict",
                                  self.value,
                                  data_rdd,
                                  batch_per_thread)
            return results.map(lambda result: Layer.convert_output(result))
        else:
            start_idx = 0
            results = []
            while start_idx < len(x):
                end_idx = min(start_idx + batch_per_thread, len(x))
                results.append(self.forward(x[start_idx:end_idx]))
                start_idx += batch_per_thread

            return np.concatenate(results, axis=0)

    @staticmethod
    def from_export_folder(folder, tf_session_config=None):
        """
        Create a TFNet from an exported folder produced by `export_tf`
        :param folder: the folder the TensorFlow model exported to
        :param tf_session_config: an optional tf.ConfigProto object to
                       set the session config in java side.
                       This config does not necessarily be the same with your current session.
                       E.g. sess_config = tf.ConfigProto(inter_op_parallelism_threads=1,
                                                         intra_op_parallelism_threads=1)
                            net = TFNet.from_session(sess, inputs, outputs, sess_config)
        :return: a TFNet
        """
        if not os.path.isdir(folder):
            raise ValueError(folder + " does not exist")
        return TFNet(folder, tf_session_config=tf_session_config)

    @staticmethod
    def from_saved_model(model_path, tag=None, signature=None,
                         inputs=None, outputs=None, tf_session_config=None):
        """
        Create a TFNet from an TensorFlow saved model
        :param model_path: the path to the SavedModel path
        :param tag: the tag to load in the saved model, default to "serve"
        :param signature: The signature of the SignatureDef that defines inputs
                          and outputs of the graph. TFNet assumes inputs is sorted
                          by their corresponding key in SignatureDef.
        :param inputs: a list input tensor names of this model, you may want to use TensorFlow's
                      command line tool to inspect the saved model to find the input tensor
                      names e.g. `saved_model_cli show --dir {saved_model_path} --all`
        :param outputs: a list output tensor names of this model, you may want to use TensorFlow's
                      command line tool to inspect the saved model to find the output tensor
                      names e.g. `saved_model_cli show --dir {saved_model_path} --all`
        :param tf_session_config: an optional tf.ConfigProto object to
                       set the session config in java side.
                       This config does not necessarily be the same with your current session.
                       E.g. sess_config = tf.ConfigProto(inter_op_parallelism_threads=1,
                                                         intra_op_parallelism_threads=1)
                            net = TFNet.from_session(sess, inputs, outputs, sess_config)
        :return: a TFNet
        """
        config_bytes = None
        if tf_session_config is not None:
            import tensorflow as tf
            assert isinstance(tf_session_config, tf.ConfigProto)
            tf_session_config.use_per_session_threads = True
            config_bytes = bytearray(tf_session_config.SerializeToString())

        if inputs is None or outputs is None:
            jvalue = callZooFunc("float", "createTFNetFromSavedModel",
                                 model_path, tag, signature, config_bytes)
        else:

            jvalue = callZooFunc("float", "createTFNetFromSavedModel",
                                 model_path, tag, inputs, outputs, config_bytes)
        return TFNet(path=None, jvalue=jvalue)

    @staticmethod
    def from_session(sess, inputs, outputs,
                     generate_backward=False,
                     allow_non_differentiable_input=True,
                     tf_session_config=None):
        """
        Create a TFNet from an a session and the inputs and outpus endpoints
        of the TensorFlow graph.
        :param sess: the TensorFlow session contain all the variables
        :param inputs: a list of TensorFlow Tensor represents the input endpoints
        of the TensorFlow graph
        :param outputs: a list of TensorFlow Tensor represents the output endpoints
        of the TensorFlow graph
        :param generate_backward: whether to generated a the backward graph, set true
        if you want to train this TFNet
        :param allow_non_differentiable_input: if set to yes, when input are not differentiable,
        the gradient will be set to zero. if set to false, an error will be thrown.
        :param tf_session_config: an optional tf.ConfigProto object to
                       set the session config in java side.
                       This config does not necessarily be the same with your current session.
                       E.g. sess_config = tf.ConfigProto(inter_op_parallelism_threads=1,
                                                         intra_op_parallelism_threads=1)
                            net = TFNet.from_session(sess, inputs, outputs, sess_config)
        :return a TFNet
        """
        from zoo.util.tf import export_tf
        temp = tempfile.mkdtemp()
        try:
            export_tf(sess, temp, inputs, outputs,
                      generate_backward, allow_non_differentiable_input)
            net = TFNet.from_export_folder(temp, tf_session_config)
        finally:
            import shutil
            shutil.rmtree(temp)

        return net
