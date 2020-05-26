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

package com.intel.analytics.zoo.serving

import com.intel.analytics.bigdl.tensor.{Storage, Tensor}
import com.intel.analytics.zoo.serving.utils.ConfigUtils
import org.scalatest.{FlatSpec, Matchers}

import scala.collection.JavaConverters._

class PreProcessingSpec extends FlatSpec with Matchers {
  "base64 string to tensor" should "work" in {
  }
  "parse shape" should "work" in {
    val shapeArray1 = ConfigUtils.parseShape("[[1,3], [3,224,224]]")
    val shapeArray2 = ConfigUtils.parseShape("[3,224,224]")
    val shapeArray3 = ConfigUtils.parseShape("3,224,224")
  }
  "create buffer" should "work" in {
    val a = Array(3, 224, 224)
  }
  "generate table" should "work" in {
    val t = List((1,2))
    def T(tuples: Tuple2[Any, Any]*): Unit = {
      tuples
    }
    T(t:_*)
  }
}
