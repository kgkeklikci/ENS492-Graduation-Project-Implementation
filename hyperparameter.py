# -*- coding: utf-8 -*-

import matplotlib.pyplot as plt
import seaborn as sns

import pandas as pd
import numpy as np
from pylab import rcParams

import tensorflow as tf
from keras import optimizers, Sequential
from keras.models import Model
from keras.utils import plot_model
from keras.layers import Dense, LSTM, RepeatVector, TimeDistributed
from keras.callbacks import ModelCheckpoint, TensorBoard

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, precision_recall_curve
from sklearn.metrics import recall_score, classification_report, auc, roc_curve
from sklearn.metrics import precision_recall_fscore_support, f1_score


SEED = 123 # used to help randomly select the data points
DATA_SPLIT_PCT = 0.2

rcParams['figure.figsize'] = 8, 6
LABELS = ["Normal","ALM Stop"]

def temporalize(X, y, lookback):
    '''
    Inputs
    X         A 2D numpy array ordered by time of shape: 
              (n_observations x n_features)
    y         A 1D numpy array with indexes aligned with 
              X, i.e. y[i] should correspond to X[i]. 
              Shape: n_observations.
    lookback  The window size to look back in the past 
              records. Shape: a scalar.

    Output
    output_X  A 3D numpy array of shape: 
              ((n_observations-lookback-1) x lookback x 
              n_features)
    output_y  A 1D array of shape: 
              (n_observations-lookback-1), aligned with X.
    '''
    output_X = []
    output_y = []
    for i in range(len(X) - lookback - 1):
        t = []
        for j in range(1, lookback + 1):
            # Gather the past records upto the lookback period
            t.append(X[[(i + j + 1)], :])
        output_X.append(t)
        output_y.append(y[i + lookback + 1])
    return np.squeeze(np.array(output_X)), np.array(output_y)

def flatten(X):
    '''
    Flatten a 3D array.
    
    Input
    X            A 3D array for lstm, where the array is sample x timesteps x features.
    
    Output
    flattened_X  A 2D array, sample x features.
    '''
    flattened_X = np.empty((X.shape[0], X.shape[2]))  # sample x features array.
    for i in range(X.shape[0]):
        flattened_X[i] = X[i, (X.shape[1]-1), :]
    return(flattened_X)

def scale(X, scaler):
    '''
    Scale 3D array.

    Inputs
    X            A 3D array for lstm, where the array is sample x timesteps x features.
    scaler       A scaler object, e.g., sklearn.preprocessing.StandardScaler, sklearn.preprocessing.normalize
    
    Output
    X            Scaled 3D array.
    '''
    for i in range(X.shape[0]):
        X[i, :, :] = scaler.transform(X[i, :, :])
        
    return X

class BATCH():
  initial = 1024
  lr_double_zero = 0.001
  lr_triple_zero = 0.0001
  

def Model(RES,batch,epochs,X_train_scaled,X_valid_scaled,X_test_scaled,lr,
          X_train,X_test,X_valid,y_train,y_test,y_valid):

  timesteps =  X_train_scaled.shape[1] # equal to the lookback
  n_features =  X_train_scaled.shape[2] # 59
  
  global model
  model = Sequential()

  # Encoder
  model.add(LSTM(128, activation='relu', dropout = 0.5, input_shape=(timesteps, n_features), return_sequences=True))
  model.add(LSTM(32, activation='relu', dropout = 0.5, return_sequences=False))
  model.add(Dense(1, activation='sigmoid'))
  # Decoder

  # model.summary()
  adam = optimizers.Adam(lr)
  model.compile(loss='binary_crossentropy', optimizer=adam, metrics=[tf.keras.metrics.AUC()])

  cp = ModelCheckpoint(filepath="lstm_classifier.h5",
                                save_best_only=True,
                                verbose=0)

  tb = TensorBoard(log_dir='./logs',
                  histogram_freq=0,
                  write_graph=True,
                  write_images=True)

  model_history = model.fit(X_train_scaled, y_train, epochs=epochs, 
                                                  batch_size=batch, shuffle = False,
                                                  validation_data=(X_valid_scaled, y_valid),
                                                  verbose=0).history

  test_x_predictions = model.predict(X_test_scaled)

  false_pos_rate, true_pos_rate, thresholds = roc_curve(y_test, test_x_predictions)
  roc_auc = auc(false_pos_rate, true_pos_rate,)

  RES.insert(0,{"AUC_SCORE": roc_auc, "LR": lr, "BATCH_SIZE": batch})

def main():
  df = pd.read_csv('/content/drive/My Drive/Pusula/features_LSTM_4_5m_full.csv')
  df = df[df.pp_mean_1 < 1000]

  # Remove time column, and the categorical columns
  df = df.drop(['time_since_last_shift_change'], axis=1)

  for _, name in enumerate(df.columns):   
      if name[0:6] == 'pp_std':
          df = df.drop([name], axis = 1)

  df = df[df.stop_type1 == 0]
  df = df[df.stop_type2 == 0]
  df = df[df.stop_type3 == 0]
  df = df[df.stop_type4 == 0]

  train_size = 0.8
  train_valid_size = 1
  train_file = df.iloc[0:int(df.shape[0]*train_size),:]
  test = df.iloc[int(df.shape[0]*train_size):,:]

  train = train_file.iloc[0:int(train_file.shape[0]*train_size),:]
  valid = train_file.iloc[int(train_file.shape[0]*train_valid_size):,:]

  # CHANGED .loc[] position
  input_X_train = train.loc[:,:'pp_mean_19'].values
  input_y_train = train['labels_stop_ALM_next_360'].values

  input_X_test = test.loc[:,:'pp_mean_19'].values
  input_y_test = test['labels_stop_ALM_next_360'].values


  input_X_valid = valid.loc[:,:'pp_mean_19'].values
  input_y_valid = valid['labels_stop_ALM_next_360'].values

  n_features = input_X_train.shape[1]  # number of features
  lookback = 10  # Equivalent to loockback*10 min of past data.

  X_train, y_train = temporalize(X = input_X_train, y = input_y_train, lookback = lookback)
  X_test, y_test = temporalize(X = input_X_test, y = input_y_test, lookback = lookback)
  X_valid, y_valid = temporalize(X = input_X_valid, y = input_y_valid, lookback = lookback)

  X_train = X_train.reshape(X_train.shape[0], lookback, n_features)
  X_valid = X_valid.reshape(X_valid.shape[0], lookback, n_features)
  X_test = X_test.reshape(X_test.shape[0], lookback, n_features)

  # Initialize a scaler using the training data.
  scaler = StandardScaler().fit(flatten(X_train))


  X_train_scaled = scale(X_train, scaler)

  a = flatten(X_train_scaled)
  print('colwise mean', np.mean(a, axis=0).round(6))
  print('colwise variance', np.var(a, axis=0))
  print()

  X_valid_scaled = scale(X_valid, scaler)

  X_test_scaled = scale(X_test, scaler)

  epochs = 25
  batch_OBJ = BATCH()
  SAMPLE_RUN = 5

  while(SAMPLE_RUN):
    # generate test samples 
    double, triple = (batch_OBJ.initial, batch_OBJ.lr_double_zero), (batch_OBJ.initial, batch_OBJ.lr_triple_zero)
    # results 
    doubleRes, tripleRes = list(), list()

    # LSTM
    Model(doubleRes,double[0],epochs,X_train_scaled,X_valid_scaled,X_test_scaled,double[1],
            X_train,X_test,X_valid,y_train,y_test,y_valid)
    # SAMPLE RESULTS 
    print("SAMPLE RUN: {0}\tBATCH: {1}\tLEARNING RATE: {2}\tAUC_SCORE: {3}".format(SAMPLE_RUN,doubleRes[0]["BATCH_SIZE"],doubleRes[0]["LR"],doubleRes[0]["AUC_SCORE"]))
    
    # LSTM
    Model(tripleRes,triple[0],epochs,X_train_scaled,X_valid_scaled,X_test_scaled,triple[1],
            X_train,X_test,X_valid,y_train,y_test,y_valid)
    # SAMPLE RESULTS 
    print("SAMPLE RUN: {0}\tBATCH: {1}\tLEARNING RATE: {2}\tAUC_SCORE: {3}".format(SAMPLE_RUN,tripleRes[0]["BATCH_SIZE"],tripleRes[0]["LR"],tripleRes[0]["AUC_SCORE"]))
      
    # last batch size will be 64 
    batch_OBJ.initial //= 2 
    SAMPLE_RUN -= 1
  print()

if __name__ == "__main__":
  main()

# BEST HYPERPARAMETERS 
"""
BATCH: 1024	LEARNING RATE: 0.001	AUC_SCORE: 0.6640736618831634
BATCH: 512	LEARNING RATE: 0.001	AUC_SCORE: 0.6054081706639168
BATCH: 128	LEARNING RATE: 0.001	AUC_SCORE: 0.6685691728172413
"""

df = pd.read_csv('/content/drive/My Drive/Pusula/features_LSTM_4_5m_full.csv')
df = df[df.pp_mean_1 < 1000]

# Remove time column, and the categorical columns
df = df.drop(['time_since_last_shift_change'], axis=1)

for _, name in enumerate(df.columns):   
    if name[0:6] == 'pp_std':
        df = df.drop([name], axis = 1)

df = df[df.stop_type1 == 0]
df = df[df.stop_type2 == 0]
df = df[df.stop_type3 == 0]
df = df[df.stop_type4 == 0]

train_size = 0.8
train_valid_size = 1
train_file = df.iloc[0:int(df.shape[0]*train_size),:]
test = df.iloc[int(df.shape[0]*train_size):,:]

train = train_file.iloc[0:int(train_file.shape[0]*train_size),:]
valid = train_file.iloc[int(train_file.shape[0]*train_valid_size):,:]

# CHANGED .loc[] position
input_X_train = train.loc[:,:'pp_mean_19'].values
input_y_train = train['labels_stop_ALM_next_360'].values

input_X_test = test.loc[:,:'pp_mean_19'].values
input_y_test = test['labels_stop_ALM_next_360'].values


input_X_valid = valid.loc[:,:'pp_mean_19'].values
input_y_valid = valid['labels_stop_ALM_next_360'].values

n_features = input_X_train.shape[1]  # number of features
lookback = 10  # Equivalent to loockback*10 min of past data.

X_train, y_train = temporalize(X = input_X_train, y = input_y_train, lookback = lookback)
X_test, y_test = temporalize(X = input_X_test, y = input_y_test, lookback = lookback)
X_valid, y_valid = temporalize(X = input_X_valid, y = input_y_valid, lookback = lookback)

X_train = X_train.reshape(X_train.shape[0], lookback, n_features)
X_valid = X_valid.reshape(X_valid.shape[0], lookback, n_features)
X_test = X_test.reshape(X_test.shape[0], lookback, n_features)

# Initialize a scaler using the training data.
scaler = StandardScaler().fit(flatten(X_train))


X_train_scaled = scale(X_train, scaler)

"""
a = flatten(X_train_scaled)
print('colwise mean', np.mean(a, axis=0).round(6))
print('colwise variance', np.var(a, axis=0))
print()
"""

X_valid_scaled = scale(X_valid, scaler)

X_test_scaled = scale(X_test, scaler)

"""
BATCH: 1024	LEARNING RATE: 0.001	AUC_SCORE: 0.6640736618831634
BATCH: 512	LEARNING RATE: 0.001	AUC_SCORE: 0.6054081706639168
BATCH: 128	LEARNING RATE: 0.001	AUC_SCORE: 0.6685691728172413
"""
lr = 0.001
epochs = 25
params = [(1024,lr,epochs),(512,lr,epochs),(128,lr,epochs)]

for _, params in enumerate(params):
  print(f"PARAM VERIFICATION: {_ + 1}")
  adam = optimizers.Adam(params[1])
  model.compile(loss='binary_crossentropy', optimizer=adam, metrics=[tf.keras.metrics.AUC()])

  cp = ModelCheckpoint(filepath="lstm_classifier.h5",
                                save_best_only=True,
                                verbose=0)

  tb = TensorBoard(log_dir='./logs',
                  histogram_freq=0,
                  write_graph=True,
                  write_images=True)

  model_history = model.fit(X_train_scaled, y_train, epochs=params[2], 
                                                  batch_size=params[0], shuffle = False,
                                                  validation_data=(X_valid_scaled, y_valid),
                                                  verbose=0).history

  test_x_predictions = model.predict(X_test_scaled)
  # precision_rt, recall_rt, threshold_rt = precision_recall_curve(y_test, test_x_predictions)

  false_pos_rate, true_pos_rate, thresholds = roc_curve(y_test, test_x_predictions)
  roc_auc = auc(false_pos_rate, true_pos_rate,)

  error_df = pd.DataFrame({'Predicted_class': np.squeeze(test_x_predictions),
                        'True_class': y_test.tolist()})
  
  threshold_fixed = 0.99
  pred_y = [1 if e > threshold_fixed else 0 for e in test_x_predictions]
  conf_matrix = confusion_matrix(error_df.True_class, pred_y)

  plt.figure(figsize=(6, 6))
  sns.heatmap(conf_matrix, xticklabels=LABELS, yticklabels=LABELS, annot=True, fmt="d");
  plt.title("Confusion matrix")
  plt.ylabel('True class')
  plt.xlabel('Predicted class')
  plt.show()

  plt.plot(false_pos_rate, true_pos_rate, linewidth=5, label='AUC = %0.3f'% roc_auc)
  plt.plot([0,1],[0,1], linewidth=5)

  plt.xlim([-0.01, 1])
  plt.ylim([0, 1.01])
  plt.legend(loc='lower right')
  plt.title('Receiver operating characteristic curve (ROC)')
  plt.ylabel('True Positive Rate')
  plt.xlabel('False Positive Rate')
  plt.show()

  # error_df.to_csv("/content/drive/My Drive/Pusula/results_AUC_" + str(roc_auc)) 
  print()

# perform the remaining tests 
"""
BATCH: 1024	LEARNING RATE: 0.0001	AUC_SCORE: 0.5653525363999314
BATCH: 512	LEARNING RATE: 0.0001	AUC_SCORE: 0.4327672464492013
BATCH: 256	LEARNING RATE: 0.001	AUC_SCORE: 0.5982646805288132
BATCH: 256	LEARNING RATE: 0.0001	AUC_SCORE: 0.4745689035078129
BATCH: 128	LEARNING RATE: 0.0001	AUC_SCORE: 0.5055839123294229
BATCH: 64	LEARNING RATE: 0.001	AUC_SCORE: 0.5021271992164708
BATCH: 64	LEARNING RATE: 0.0001	AUC_SCORE: 0.597507161444097
"""
epochs = 25
params = [(1024,0.0001,epochs),(512,0.0001,epochs),(256,0.001,epochs),(256,0.0001,epochs),
          (128,0.0001,epochs),(64,0.001,epochs),(64,0.0001,epochs)]

for _, params in enumerate(params):
  print(f"PARAM VERIFICATION: {_ + 1}")
  adam = optimizers.Adam(params[1])
  model.compile(loss='binary_crossentropy', optimizer=adam, metrics=[tf.keras.metrics.AUC()])

  cp = ModelCheckpoint(filepath="lstm_classifier.h5",
                                save_best_only=True,
                                verbose=0)

  tb = TensorBoard(log_dir='./logs',
                  histogram_freq=0,
                  write_graph=True,
                  write_images=True)

  model_history = model.fit(X_train_scaled, y_train, epochs=params[2], 
                                                  batch_size=params[0], shuffle = False,
                                                  validation_data=(X_valid_scaled, y_valid),
                                                  verbose=0).history

  test_x_predictions = model.predict(X_test_scaled)
  # precision_rt, recall_rt, threshold_rt = precision_recall_curve(y_test, test_x_predictions)

  false_pos_rate, true_pos_rate, thresholds = roc_curve(y_test, test_x_predictions)
  roc_auc = auc(false_pos_rate, true_pos_rate,)

  error_df = pd.DataFrame({'Predicted_class': np.squeeze(test_x_predictions),
                        'True_class': y_test.tolist()})
  
  threshold_fixed = 0.99
  pred_y = [1 if e > threshold_fixed else 0 for e in test_x_predictions]
  conf_matrix = confusion_matrix(error_df.True_class, pred_y)

  plt.figure(figsize=(6, 6))
  sns.heatmap(conf_matrix, xticklabels=LABELS, yticklabels=LABELS, annot=True, fmt="d");
  plt.title("Confusion matrix")
  plt.ylabel('True class')
  plt.xlabel('Predicted class')
  plt.show()

  plt.plot(false_pos_rate, true_pos_rate, linewidth=5, label='AUC = %0.3f'% roc_auc)
  plt.plot([0,1],[0,1], linewidth=5)

  plt.xlim([-0.01, 1])
  plt.ylim([0, 1.01])
  plt.legend(loc='lower right')
  plt.title('Receiver operating characteristic curve (ROC)')
  plt.ylabel('True Positive Rate')
  plt.xlabel('False Positive Rate')
  plt.show()

  # error_df.to_csv("/content/drive/My Drive/Pusula/results_AUC_" + str(str(roc_auc))) 
  print()