/*
 * Copyright 2018 Analytics Zoo Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.intel.analytics.zoo.serving.engine

import com.intel.analytics.bigdl.nn.abstractnn.Activity
import com.intel.analytics.bigdl.tensor.Tensor
import com.intel.analytics.bigdl.utils.T
import com.intel.analytics.zoo.serving.PostProcessing
import com.intel.analytics.zoo.serving.utils.SerParams

object InferenceSupportive {
  def multiThreadInference(preProcessed: Iterator[(String, Activity)],
                           params: SerParams): Iterator[(String, String)] = {
    val postProcessed = preProcessed.grouped(params.coreNum).flatMap(pathByteBatch => {
      val thisBatchSize = pathByteBatch.size
//      val t = if (params.chwFlag) {
//        Tensor[Float](params.coreNum, params.C, params.H, params.W)
//      } else {
//        Tensor[Float](params.coreNum, params.H, params.W, params.C)
//      }
//
//      (0 until thisBatchSize).toParArray.foreach(i =>
//        t.select(1, i + 1).copy(pathByteBatch(i)._2))
//
//      val thisT = if (params.chwFlag) {
//        t.resize(thisBatchSize, params.C, params.H, params.W)
//      } else {
//        t.resize(thisBatchSize, params.H, params.W, params.C)
//      }
//      val x = if (params.modelType == "openvino") {
//        thisT.addSingletonDimension()
//      } else {
//        thisT
//      }
      val t = batchInput(pathByteBatch, params)
      /**
       * addSingletonDimension method will modify the
       * original Tensor, thus if reuse of Tensor is needed,
       * have to squeeze it back.
       */
//      println(s"preparing to predict")
      val result = if (params.modelType == "openvino") {
        val res = params.model.doPredict(t).toTensor[Float].squeeze()
        if (t.isTensor) {
          t.toTensor[Float].squeeze(1)
        }
        else if (t.isTable) {
          val dataTable = t.toTable
          dataTable.keySet.foreach(key => {
            dataTable(key).asInstanceOf[Tensor[Float]].squeeze(1)
          })
        }
        res.squeeze(1)
      } else {
        params.model.doPredict(t).toTensor[Float]
      }
//      println(s"predict end")
      (0 until thisBatchSize).toParArray.map(i => {
        val value = PostProcessing(result.select(1, i + 1), params.filter)
        (pathByteBatch(i)._1, value)
      })
    })
    postProcessed
  }
  def batchInput(seq: Seq[(String, Activity)],
    params: SerParams): Activity = {
    val thisBatchSize = seq.size

    val kvTuples = seq.head._2.toTable.keySet.foreach(key => {

    })
    val t = T.array(params.dataShape.map(shape => {
      Tensor[Float](params.coreNum +: shape)
    }))
    (0 until thisBatchSize).toParArray.foreach(i => {
      val dataTable = seq(i)._2.toTable
      t.keySet.foreach(key => {
        t(key).asInstanceOf[Tensor[Float]].select(1, i + 1)
          .copy(dataTable(key).asInstanceOf[Tensor[Float]])
        if (params.modelType == "openvino") {
          t(key).asInstanceOf[Tensor[Float]].addSingletonDimension()
        }
      })
    })
    if (params.dataShape.length == 1) {
      t.keySet.foreach(key => {
        return t(key).asInstanceOf[Tensor[Float]]
      })
    }
    t
  }
}
