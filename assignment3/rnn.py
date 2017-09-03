import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import math
import time
import itertools
import shutil
from datetime import datetime
import tensorflow as tf
from tensorflow.python.client import timeline
import tree as tr
import pdb
from utils import Vocab


RESET_AFTER = 100 #50
class Config(object):
    """Holds model hyperparams and data information.
       Model objects are passed a Config() object at instantiation.
    """
    embed_size = 35
    label_size = 2
    early_stopping = 2
    anneal_threshold = 0.99
    anneal_by = 1.5
    max_epochs = 30
    lr = 0.01
    l2 = 0.02
    model_name = 'rnn_embed=%d_l2=%f_lr=%f.weights'%(embed_size, l2, lr)
    root_logdir = './logs'


class RNN_Model():

    def load_data(self):
        """Loads train/dev/test data and builds vocabulary."""
        # the training data was originally 700
        self.train_data, self.dev_data, self.test_data = tr.simplified_data(700, 100, 200)
        # build vocab from training data
        self.vocab = Vocab()
        train_sents = [t.get_words() for t in self.train_data]
        self.vocab.construct(list(itertools.chain.from_iterable(train_sents)))

    def setup_logging(self):
        """Sets up some parameters for the logging of the current model"""
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        self.logdir = "{}/run-{}/".format(self.config.root_logdir, now)


    def inference(self, tree, predict_only_root=False):
        """For a given tree build the RNN models computation graph up to where it
            may be used for inference.
        Args:
            tree: a Tree object on which to build the computation graph for the RNN
        Returns:
            softmax_linear: Output tensor with the computed logits.
        """
        node_tensors = self.add_model(tree.root)
        if predict_only_root:
            node_tensors = node_tensors[tree.root]
        else:
            node_tensors = [tensor for node, tensor in node_tensors.items() if node.label!=2]
            node_tensors = [tf.reshape(tensor, [1, self.config.embed_size]) for
tensor in node_tensors]
            node_tensors = tf.concat(node_tensors, axis=0)
        return self.add_projections(node_tensors)

    def add_model_vars(self):
        '''
        You model contains the following parameters:
            embedding:  tensor(vocab_size, embed_size)
            W1:         tensor(2* embed_size, embed_size)
            b1:         tensor(1, embed_size)
            U:          tensor(embed_size, output_size)
            bs:         tensor(1, output_size)
        Hint: Add the tensorflow variables to the graph here and *reuse* them while building
                the compution graphs for composition and projection for each tree
        Hint: Use a variable_scope "Composition" for the composition layer, and
              "Projection") for the linear transformations preceding the softmax.
        '''
        with tf.variable_scope('Composition'):
            ### YOUR CODE HERE
            embedding = tf.get_variable("embedding", shape=(len(self.vocab), self.config.embed_size))
            w1 = tf.get_variable("w1", shape=(2 * self.config.embed_size,
self.config.embed_size))
            b1 = tf.get_variable("b1", shape=(1, self.config.embed_size))
            ### END YOUR CODE
        with tf.variable_scope('Projection'):
            ### YOUR CODE HERE
            # We have two classes for the output
            U = tf.get_variable("U", shape=(self.config.embed_size, 2))
            bs = tf.get_variable("bs", shape=(1, 2))
            ### END YOUR CODE

    def add_model(self, node):
        """Recursively build the model to compute the phrase embeddings in the tree

        Hint: Refer to tree.py and vocab.py before you start. Refer to
              the model's vocab with self.vocab
        Hint: Reuse the "Composition" variable_scope here
        Hint: Store a node's vector representation in node.tensor so it can be
              used by it's parent
        Hint: If node is a leaf node, it's vector representation is just that of the
              word vector (see tf.gather()).
        Args:
            node: a Node object
        Returns:
            node_tensors: Dict: key = Node, value = tensor(1, embed_size)
        """
        with tf.variable_scope('Composition', reuse=True):
            ### YOUR CODE HERE
            w1 = tf.get_variable("w1")
            b1 = tf.get_variable("b1")
            embedding = tf.get_variable("embedding")
            ### END YOUR CODE

        node_tensors = dict()
        curr_node_tensor = None

        if node.isLeaf:
            ### YOUR CODE HERE
            #tr.print_leaf(node)
            # this code should assign to curr_node_tensor a vector representation of the leaf node.

            #node.tensor = tf.gather([self.vocab.encode(node.word)],
            #range(self.config.embed_size))
            #node.tensor = tf.cast(node.tensor, dtype=tf.float32)

            # Going to try this with an actual word embedding
            #embeddings = tf.Variable(
#tf.random_uniform([len(self.vocab), self.config.embed_size], -1.0, 1.0))
            node.tensor = tf.nn.embedding_lookup(embedding,
self.vocab.encode(node.word))

            curr_node_tensor = node.tensor
            ### END YOUR CODE
        else:
            #tr.print_root(node)
            # this will cause an update to the dictionary node_tensor[node.left] ==
            # self.add_model(node.left)
            node_tensors.update(self.add_model(node.left))
            node_tensors.update(self.add_model(node.right))
            ### YOUR CODE HERE
            # This attempt tried to stack the models recursively which would
            # unravel the stack all the way to the leaves to get the tensor
            # value from the word vectors.
            #hidden_layer = tf.stack(self.add_model(node.left),
            #self.add_model(node.right)) * w1 + b1

            # This attempt tries to calculate the root's tensor just from the
            # left and right leaves and relies on there being a node.tensor
            # property in each one.
            # Note here I had at first used tf.stack (think stacking the tensors
            # one on top of the other) but based on feedback from the resulting
            # shape I had instead used a concat
            node.left.tensor = tf.reshape(node.left.tensor, [-1,
self.config.embed_size])
            node.right.tensor = tf.reshape(node.right.tensor, [-1,
self.config.embed_size])
            concatenated_tensors = tf.concat([node.left.tensor,
node.right.tensor], axis=0)
            # reshape so that matmul will work, the result will be a [1,70]
            # tensor
            reshaped_tensors = tf.reshape(concatenated_tensors, [-1,
2*self.config.embed_size])
            # the output here is [1,35] if embed_size is 35
            node.tensor = tf.matmul(reshaped_tensors, w1) + b1
            #TODO: this probably has to be node.tensor
            # prior to node.tensor this was just curr_node_tensor
            node.tensor =  tf.maximum(node.tensor, tf.zeros(shape=(1,
self.config.embed_size)))
            curr_node_tensor = node.tensor
            ### END YOUR CODE
        node_tensors[node] = curr_node_tensor
        return node_tensors


    def add_projections(self, node_tensors):
        """Add projections to the composition vectors to compute the raw sentiment scores

        Hint: Reuse the "Projection" variable_scope here
        Args:
            node_tensors: tensor(?, embed_size)
            When we are evaluating just on the root node then the first
            dimension would be 1, if we are looking through a hierarchy of terms in a
            sentence then that would be equal to the number of words we want to include i.e.
            5
        Returns:
            output: tensor(?, label_size)
        """
        logits = None
        ### YOUR CODE HERE
        with tf.variable_scope('Projection', reuse=True):
            U = tf.get_variable("U")
            bs = tf.get_variable("bs")
        logits = tf.matmul(node_tensors, U) + bs
        ### END YOUR CODE
        return logits

    def loss(self, logits, labels):
        """Adds loss ops to the computational graph.

        Hint: Use sparse_softmax_cross_entropy_with_logits
        Hint: Remember to add l2_loss (see tf.nn.l2_loss)
        Args:
            logits: tensor(num_nodes, output_size)
            labels: python list, len = num_nodes
        Returns:
            loss: tensor 0-D
        """
        loss = None
        # YOUR CODE HERE
        # sparse softmax returns a tensor of dimension 1-D with the number of
        # elements in the batch which is the first dimention of logits and the
        # only dimention of labels. In a sentence with 5 words this dimention
        # will be 5 because the accuracy of our prediction with regard to each
        # word is returned.
        # As our stated goal is to return a 0-D tensor let's do thee next best
        # thing and take a mean of all of the accuracies.
        loss = tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(labels=labels,
logits=logits, name="sparse_softmax_loss")) + tf.nn.l2_loss(logits)
        # END YOUR CODE
        return loss

    def training(self, loss):
        """Sets up the training Ops.

        Creates an optimizer and applies the gradients to all trainable variables.
        The Op returned by this function is what must be passed to the
        `sess.run()` call to cause the model to train. See

        https://www.tensorflow.org/versions/r0.7/api_docs/python/train.html#Optimizer

        for more information.

        Hint: Use tf.train.GradientDescentOptimizer for this model.
                Calling optimizer.minimize() will return a train_op object.

        Args:
            loss: tensor 0-D
        Returns:
            train_op: tensorflow op for training.
        """
        train_op = None
        # YOUR CODE HERE
        #trainer = tf.train.GradientDescentOptimizer(self.config.lr,
#name="gradient_descent")
        trainer = tf.train.MomentumOptimizer(learning_rate=self.config.lr,
momentum=0.9, use_nesterov=True, name="nesterov_momentum_optimizer")
        train_op = trainer.minimize(loss, name="minimize_loss")
        # END YOUR CODE
        return train_op

    def predictions(self, y):
        """Returns predictions from sparse scores

        Args:
            y: tensor(?, label_size)
        Returns:
            The highest scoring label where each label is a score of Negate,
Neutral, Positive. This HW uses only two labels: negative and positive
            predictions: tensor(?,1)
        """
        predictions = None
        # YOUR CODE HERE
        # NOTE This looks to only return 0s, something smells
        #predictions = tf.argmax(tf.nn.softmax(y))
        #predictions = tf.argmax(y)
        # However this works so supplying the axis is important
        predictions = tf.argmax(y, axis=1, name="prediction")
        # END YOUR CODE
        return predictions

    def __init__(self, config):
        self.config = config
        self.load_data()
        self.setup_logging()

    def predict(self, trees, weights_path, get_loss = False):
        """Make predictions from the provided model."""
        results = []
        losses = []
        for i in range(int(math.ceil(len(trees)/float(RESET_AFTER)))):
            with tf.Graph().as_default(), tf.Session() as sess:
                self.add_model_vars()
                saver = tf.train.Saver()
                saver.restore(sess, weights_path)
                for tree in trees[i*RESET_AFTER: (i+1)*RESET_AFTER]:
                    logits = self.inference(tree, True)
                    predictions = self.predictions(logits)
                    root_prediction = sess.run(predictions)[0]
                    if get_loss:
                        root_label = tree.root.label
                        loss = sess.run(self.loss(logits, [root_label]))
                        losses.append(loss)
                    results.append(root_prediction)
        return results, losses

    def run_epoch(self, new_model = False, verbose=10):
        step = 0
        loss_history = []
        run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
        run_metadata = tf.RunMetadata()
        # Set to True to look at placement
        config = tf.ConfigProto(log_device_placement=False)
        while step < len(self.train_data):
            with tf.Graph().as_default(), tf.Session(config=config) as sess:
                self.add_model_vars()
                if new_model:
                    init = tf.global_variables_initializer()
                    sess.run(init)
                else:
                    saver = tf.train.Saver()
                    saver.restore(sess, './weights/%s.temp'%self.config.model_name)
                # The RESET_AFTER essentially controls batching of our training
                # When RESET_AFTER == len(self.train_data) then this is for loop
                # is executed once. Otherwise it is run len(self.train_data /
                # RESET_AFTER)
                # This allows to save the trained model parameters every
                # RESET_AFTER
                for _ in range(RESET_AFTER):
                    if step>=len(self.train_data):
                        break
                    tree = self.train_data[step]
                    logits = self.inference(tree)
                    labels = [l for l in tree.labels if l!=2]
                    loss = self.loss(logits, labels)
                    train_op = self.training(loss)
                    loss, _ = sess.run([loss, train_op], options=run_options, run_metadata=run_metadata)
                    loss_history.append(loss)
                    if (step % verbose)==0:
                        sys.stdout.write('\r{} / {} :    loss = {}'.format(
                            step, len(self.train_data), np.mean(loss_history)))
                        sys.stdout.flush()
                        loss_summary = tf.summary.scalar('loss', loss)
                        file_writer = tf.summary.FileWriter(self.logdir, tf.get_default_graph())
                        summary_str = loss_summary.eval()
                        file_writer.add_summary(summary_str, step)
                    step += 1

                saver = tf.train.Saver()
                if not os.path.exists("./weights"):
                    os.makedirs("./weights")
                saver.save(sess, './weights/%s.temp'%self.config.model_name)
                # write timeline data for debugging
                #tl = timeline.Timeline(run_metadata.step_stats)
                #ctf = tl.generate_chrome_trace_format()
                #with open('timeline.json', 'w') as f:
                #    f.write(ctf)

        train_preds, _ = self.predict(self.train_data, './weights/%s.temp'%self.config.model_name)
        val_preds, val_losses = self.predict(self.dev_data, './weights/%s.temp'%self.config.model_name, get_loss=True)
        train_labels = [t.root.label for t in self.train_data]
        val_labels = [t.root.label for t in self.dev_data]
        train_acc = np.equal(train_preds, train_labels).mean()
        val_acc = np.equal(val_preds, val_labels).mean()
        file_writer.close()
        #train_summary = tf.summary.scalar('train accuracy', train_acc)
        #val_summary = tf.summary.scalar('val accuracy', val_acc)
        print()
        print('Training acc (only root node): {}'.format(train_acc))
        print( 'Valiation acc (only root node): {}'.format(val_acc))
        print( self.make_conf(train_labels, train_preds))
        print( self.make_conf(val_labels, val_preds))
        return train_acc, val_acc, loss_history, np.mean(val_losses)

    def train(self, verbose=True):
        complete_loss_history = []
        train_acc_history = []
        val_acc_history = []
        prev_epoch_loss = float('inf')
        best_val_loss = float('inf')
        best_val_epoch = 0
        stopped = -1
        for epoch in range(self.config.max_epochs):
            print('epoch {}'.format(epoch))
            if epoch==0:
                train_acc, val_acc, loss_history, val_loss = self.run_epoch(new_model=True)
            else:
                train_acc, val_acc, loss_history, val_loss = self.run_epoch()
            complete_loss_history.extend(loss_history)
            train_acc_history.append(train_acc)
            val_acc_history.append(val_acc)

            #lr annealing
            epoch_loss = np.mean(loss_history)
            if epoch_loss>prev_epoch_loss*self.config.anneal_threshold:
                self.config.lr/=self.config.anneal_by
                print('annealed lr to %f'%self.config.lr)
            prev_epoch_loss = epoch_loss

            #save if model has improved on val
            if val_loss < best_val_loss:
                 shutil.copyfile('./weights/%s.temp.data-00000-of-00001'%self.config.model_name, './weights/%s.data-00000-of-00001'%self.config.model_name)
                 shutil.copyfile('./weights/%s.temp.index'%self.config.model_name, './weights/%s.index'%self.config.model_name)
                 shutil.copyfile('./weights/%s.temp.meta'%self.config.model_name, './weights/%s.meta'%self.config.model_name)

                 best_val_loss = val_loss
                 best_val_epoch = epoch

            # if model has not imprvoved for a while stop
            if epoch - best_val_epoch > self.config.early_stopping:
                stopped = epoch
                #break
        if verbose:
                sys.stdout.write('\r')
                sys.stdout.flush()

        print('\n\nstopped at {}\n'.format(stopped))
        return {
            'loss_history': complete_loss_history,
            'train_acc_history': train_acc_history,
            'val_acc_history': val_acc_history,
            }

    def make_conf(self, labels, predictions):
        confmat = np.zeros([2, 2])
        for l,p in zip(labels, predictions):
            confmat[l, p] += 1
        return confmat


def test_RNN():
    """Test RNN model implementation.

    You can use this function to test your implementation of the Named Entity
    Recognition network. When debugging, set max_epochs in the Config object to 1
    so you can rapidly iterate.
    """
    config = Config()
    model = RNN_Model(config)
    start_time = time.time()
    stats = model.train(verbose=True)
    print('Training time: {}'.format(time.time() - start_time))

    plt.plot(stats['loss_history'])
    plt.title('Loss history')
    plt.xlabel('Iteration')
    plt.ylabel('Loss')
    plt.savefig("loss_history.png")
    plt.show()

    print('Test')
    print('=-=-=')
    predictions, _ = model.predict(model.test_data, './weights/%s.temp'%model.config.model_name)
    labels = [t.root.label for t in model.test_data]
    test_acc = np.equal(predictions, labels).mean()
    print('Test acc: {}'.format(test_acc))

if __name__ == "__main__":
        test_RNN()
