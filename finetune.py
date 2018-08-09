"""Script to finetune AlexNet using Tensorflow.

With this script you can finetune AlexNet as provided in the alexnet.py
class on any given dataset. Specify the configuration settings at the
beginning according to your problem.
This script was written for TensorFlow >= version 1.2rc0 and comes with a blog
post, which you can find here:

https://kratzert.github.io/2017/02/24/finetuning-alexnet-with-tensorflow.html

Author: Frederik Kratzert
contact: f.kratzert(at)gmail.com
"""

import os

import numpy as np
import tensorflow as tf

from alexnet import AlexNet
from datagenerator import ImageDataGenerator
from datetime import datetime
import time

"""
Configuration Part.
"""

# Path to the textfiles for the trainings and validation set
train_file = 'data/train.txt'
val_file = 'data/val.txt'

# Learning params
learning_rate = 0.001
num_epochs = 100
batch_size = 32

# Network params
dropout_rate = 0.5
num_classes = 4
train_layers = ['fc8', 'fc7', 'fc6']

# How often we want to write the tf.summary data to disk
display_step = 20

# Path for tf.summary.FileWriter and to store model checkpoints
filewriter_path = "result/tensorboard"
checkpoint_path = "result/checkpoints"

"""
Main Part of the finetuning Script.
"""

# Create parent path if it doesn't exist
if not os.path.exists(checkpoint_path):
    os.makedirs(checkpoint_path)

# Create parent path if it doesn't exist
if not os.path.exists(filewriter_path):
    os.mkdir(filewriter_path)

# Place data loading and preprocessing on the cpu
with tf.device('/cpu:0'):
    tr_data = ImageDataGenerator(train_file,
                                 mode='training',
                                 batch_size=batch_size,
                                 num_classes=num_classes,
                                 shuffle=True)

    val_data = ImageDataGenerator(val_file,
                                  mode='inference',
                                  batch_size=batch_size,
                                  num_classes=num_classes,
                                  shuffle=False)

    # create an reinitializable iterator given the dataset structure
    iterator = tf.data.Iterator.from_structure(tr_data.data.output_types, tr_data.data.output_shapes)
    print(tr_data.data.output_types, tr_data.data.output_shapes)
    next_batch = iterator.get_next()

# Ops for initializing the two different iterators
training_init_op = iterator.make_initializer(tr_data.data)
validation_init_op = iterator.make_initializer(val_data.data)

# TF placeholder for graph input and output
x = tf.placeholder(tf.float32, [batch_size, 227, 227, 3])
y = tf.placeholder(tf.float32, [batch_size, num_classes])
keep_prob = tf.placeholder(tf.float32)

# Initialize model
model = AlexNet(x, keep_prob, num_classes, train_layers)

# Link variable to model output
score = model.fc8

# List of trainable variables of the layers we want to train
var_list = [v for v in tf.trainable_variables() if v.name.split('/')[0] in train_layers]
print(var_list)

# Op for calculating the loss
with tf.name_scope("cross_ent"):
    loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=score,
                                                                  labels=y))

# Train op
with tf.name_scope("train"):
    # Get gradients of all trainable variables
    gradients = tf.gradients(loss, var_list)
    gradients = list(zip(gradients, var_list))

    # Create optimizer and apply gradient descent to the trainable variables
    # optimizer = tf.train.GradientDescentOptimizer(learning_rate)
    optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate)
    train_op = optimizer.apply_gradients(grads_and_vars=gradients)

# Add gradients to summary
for gradient, var in gradients:
    tf.summary.histogram(var.name + '/gradient', gradient)

# Add the variables we train to the summary
# for var in var_list:
#     tf.summary.histogram(var.name, var)

# Add the loss to summary
tf.summary.scalar('cross_entropy', loss)

# Evaluation op: Accuracy of the model
with tf.name_scope("accuracy"):
    correct_pred = tf.equal(tf.argmax(score, 1), tf.argmax(y, 1))
    accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

# Add the accuracy to the summary
tf.summary.scalar('accuracy', accuracy)

# Merge all summaries together
merged_summary = tf.summary.merge_all()

# Initialize the FileWriter
writer = tf.summary.FileWriter(filewriter_path)

# Initialize an saver for store model checkpoints
saver = tf.train.Saver()

# Get the number of training/validation steps per epoch
train_batches_per_epoch = int(np.floor(tr_data.data_size / batch_size))
val_batches_per_epoch = int(np.floor(val_data.data_size / batch_size))

# Start Tensorflow session
with tf.Session() as sess:
    # Initialize all variables
    sess.run(tf.global_variables_initializer())

    # Add the model graph to TensorBoard
    writer.add_graph(sess.graph)

    # Load the pretrained weights into the non-trainable layer
    model.load_initial_weights(sess)

    print("{} Start training...".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print("{} Open Tensorboard at --logdir {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                      filewriter_path))

    # Loop over number of epochs
    for epoch in range(num_epochs):

        print("{} Epoch number: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), epoch + 1))

        start_time = time.time()

        # Initialize iterator with the training dataset
        sess.run(training_init_op)
        total_loss = 0
        total_acc = 0
        for step in range(train_batches_per_epoch):
            # get next batch of data
            img_batch, label_batch = sess.run(next_batch)

            # And run the training op
            _, _loss, _acc = sess.run([train_op, loss, accuracy], feed_dict={x: img_batch,
                                                                             y: label_batch,
                                                                             keep_prob: dropout_rate})
            total_loss += _loss
            total_acc += _acc

        avg_loss = total_loss / train_batches_per_epoch
        avg_acc = total_acc / train_batches_per_epoch

        # Generate summary with the current batch of data and write to file
        # if step % display_step == 0:
        #     s = sess.run(merged_summary, feed_dict={x: img_batch,
        #                                             y: label_batch,
        #                                             keep_prob: 1.})
        #
        #     writer.add_summary(s, epoch*train_batches_per_epoch + step)

        print('{} Use time:{:.0f} s, loss:{:.4f}, acc:{:.4f}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                                     time.time() - start_time,
                                                                     avg_loss, avg_acc))
        # Validate the model on the entire validation set
        print("{} Start validation".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        sess.run(validation_init_op)
        test_acc = 0.
        test_loss = 0
        for _ in range(val_batches_per_epoch):
            img_batch, label_batch = sess.run(next_batch)
            los, acc = sess.run([loss, accuracy], feed_dict={x: img_batch,
                                                             y: label_batch,
                                                             keep_prob: 1.})
            test_acc += acc
            test_loss += los

        test_acc /= val_batches_per_epoch
        test_loss /= val_batches_per_epoch
        print("{} Validation Accuracy = {:.4f}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                       test_acc))
        if (epoch + 1) % 5 == 0:
            print("{} Saving checkpoint of model...".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # save checkpoint of the model
            ckpt_name = 'model_epoch_{}_evalLoss_{:.2f}_evalAcc_{:.2f}.ckpt'.format(epoch + 1, test_loss, test_acc)
            ckpt_path = os.path.join(checkpoint_path, ckpt_name)
            save_path = saver.save(sess, ckpt_path)

            print("{} Model checkpoint saved at {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                           ckpt_path))
